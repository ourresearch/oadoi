import logging
import os
import re
import threading
import time
from base64 import standard_b64decode
from threading import current_thread
from typing import List

import requests
from requests import Request, PreparedRequest, Response
from sqlalchemy import Column, Integer, Enum, String, JSON, ForeignKey
from sqlalchemy.orm import relationship
from tenacity import Retrying, stop_after_attempt, wait_exponential

from app import db
from const import ZYTE_API_URL, ZYTE_API_KEY
from pdf_util import is_pdf
from redirectors import ALL_REDIRECTORS
from util import is_bad_landing_page

CRAWLERA_PROXY = 'http://{}:DUMMY@impactstory.crawlera.com:8010'.format(
    os.getenv("CRAWLERA_KEY"))

_DEFAULT_ZYTE_PARAMS = {"httpResponseBody": True, "httpResponseHeaders": True}


class ZytePolicy(db.Model):
    __tablename__ = 'zyte_policies'

    id = Column(Integer, primary_key=True)
    type = Column(
        Enum('url', 'doi', name='zyte_policy_type_enum'),
        nullable=False, default='url')
    regex = Column(String(50), nullable=False)
    profile = Column(Enum('proxy', 'api', 'bypass', name='zyte_profile_enum'),
                     nullable=False, default='proxy')
    params = Column(JSON, nullable=True, default={})
    priority = Column(Integer, default=1, nullable=False)

    parent_id = Column(Integer, ForeignKey('zyte_policies.id'), nullable=True)
    parent = relationship('ZytePolicy', remote_side=[id])

    # children = relationship('ZytePolicy', backref='parent', remote_side=[id])

    def __str__(self):
        return f'<ZytePolicy id={self.id} type={self.type} regex={self.regex} profile={self.profile} priority={self.priority}>'

    def __repr__(self):
        return self.__str__()

    def match(self, doi_or_domain):
        return bool(re.search(self.regex, doi_or_domain))

    def sender(self, session):
        def _sender(request: PreparedRequest,
                    *args,
                    **kwargs, ):
            if self.profile == 'api':
                return _get_zyte_api_response(request.url,
                                              self.params,
                                              session=session.api_session,
                                              **kwargs)
            elif self.profile == 'proxy':
                proxies = {'http': CRAWLERA_PROXY, 'https': CRAWLERA_PROXY}
                kwargs['proxies'] = proxies
                kwargs['verify'] = False
                request.headers['X-Crawlera-Profile'] = 'desktop'
                return super(session.__class__, session).send(request,
                                                              *args,
                                                              **kwargs)
            elif self.profile == 'bypass':
                return super(session.__class__, session).send(request,
                                                              *args,
                                                              **kwargs)
            else:
                raise ValueError(f'Invalid ZyteProfile type: {self.type}')

        return _sender


_ALL_POLICIES: List[ZytePolicy] = ZytePolicy.query.all()
_REFRESH_LOCK = threading.Lock()  # Lock to ensure thread safety
_REFRESH_THREAD = None  # Reference to the refresh thread
DEFAULT_FALLBACK_POLICIES = [ZytePolicy(profile='proxy', id=1000),
                             ZytePolicy(profile='api', parent_id=1000)]
BYPASS_POLICY = ZytePolicy(profile='bypass')


def _refresh_policies():
    global _ALL_POLICIES
    while True:
        _ALL_POLICIES = ZytePolicy.query.all()
        time.sleep(5 * 60)


def start_refresh_thread():
    global _REFRESH_THREAD
    global _REFRESH_LOCK
    with _REFRESH_LOCK:
        # Check if the thread is already running
        if _REFRESH_THREAD is None or not _REFRESH_THREAD.is_alive():
            _REFRESH_THREAD = threading.Thread(target=_refresh_policies)
            _REFRESH_THREAD.start()


def get_matching_policies(url):
    matching_policies = [policy for policy in _ALL_POLICIES if
                         policy.match(url)]
    if not matching_policies:
        return []
    parent_policies = sorted(
        [policy for policy in matching_policies if policy.parent_id is None],
        key=lambda policy: (
            policy.type == 'api' and policy.params is not None,
            policy.type == 'api',
            policy.type == 'proxy'
        )
    )
    if len(parent_policies) > 1 and parent_policies[0].params is not None and parent_policies[1].params is not None:
        raise Exception(
            f'Colliding policies for URL: {url} - {parent_policies}')
    parent_policy = parent_policies[0]
    retry_policies = sorted(
        [policy for policy in matching_policies if
         policy.parent_id == parent_policy.id],
        key=lambda policy: (
            policy.type == 'api' and policy.params is not None,
            policy.type == 'api',
            policy.type == 'proxy'
        )
    )
    return [parent_policy] + retry_policies


def _zyte_params_to_req(url, zyte_params):
    req = PreparedRequest()
    req.method = zyte_params.get('httpRequestMethod', "GET")
    req.url = url
    req.headers = zyte_params.get('customHttpRequestHeaders')
    return req


def _get_zyte_api_response(url, zyte_params, session: requests.Session = None,
                           **kwargs):
    if not zyte_params:
        zyte_params = _DEFAULT_ZYTE_PARAMS
    zyte_params['url'] = url
    if not session:
        session = requests
    r = session.post(ZYTE_API_URL, auth=(ZYTE_API_KEY, ''),
                     json=zyte_params, **kwargs)
    r.raise_for_status()
    j = r.json()
    response = requests.Response()
    response.status_code = j['statusCode']
    response._content = j.get('browserHtml',
                              '').encode() or standard_b64decode(
        j.get('httpResponseBody'))
    response.url = j['url']
    for header in j.get('httpResponseHeaders', []):
        response.headers[header['name']] = header['value']
    response.request = _zyte_params_to_req(url, zyte_params)
    if not response.ok and 'meta name="citation_publisher" content="IOP Publishing"' in response.text:
        response.status_code = 200
    return response


def make_before_cb(url, policy, logger: logging.Logger):
    def before_logger(retry_state):
        logger.debug(
            f'Trying attempt #{retry_state.attempt_number} with URL: {url} ({policy})')

    return before_logger


def make_after_cb(url, logger: logging.Logger):
    def after_logger(retry_state):
        if retry_state.outcome.failed:
            exception = retry_state.outcome.exception()
            logger.warning(
                f"Exception {type(exception)}: {str(exception)} during retry attempt {retry_state.attempt_number}")
        logger.debug(
            f'URL {url} has taken {retry_state.seconds_since_start}s so far (attempt #{retry_state.attempt_number})')

    return after_logger


_DEFAULT_RETRY = Retrying(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.5, min=1, max=10),
    reraise=True,
)


class BadLandingPageException(Exception):
    pass


class ZyteSession(requests.Session):

    @classmethod
    def make_logger(cls, thread_n, level=logging.DEBUG):
        logger = logging.getLogger(f'zyte_session-{thread_n}')
        logger.setLevel(level)
        # fh = logging.FileHandler(f'log_{org_id}.log', 'w')
        # fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '[%(name)s | %(asctime)s] %(levelname)s - %(message)s')
        # fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # LOGGER.addHandler(fh)
        logger.addHandler(ch)
        logger.propagate = False
        return logger

    def __init__(self,
                 policies: List[ZytePolicy] = None,
                 fallback_policies: List[ZytePolicy] = None,
                 retry: Retrying = _DEFAULT_RETRY,
                 logger: logging.Logger = None):
        self.policies = sorted(policies, key=lambda p: p.priority,
                               reverse=False) if policies else None
        self.fallback_policies = sorted(fallback_policies,
                                        key=lambda p: p.priority,
                                        reverse=False) if fallback_policies else [
            BYPASS_POLICY]
        self.api_session = requests.Session()
        self.retry = retry
        self.logger = logger if logger else self.make_logger(
            current_thread().name)
        super().__init__()

    def get(
            self,
            url,
            zyte_policies=None,
            fixed_policies=False,
            **kwargs,
    ):
        return self.request('GET', url, zyte_policies=zyte_policies,
                            fixed_policies=fixed_policies, **kwargs)

    def get_redirect_target(self, resp):
        if is_pdf(resp.content):
            return None
        for redirector in ALL_REDIRECTORS:
            if target := redirector(resp):
                return target
        return super().get_redirect_target(resp)

    def request(
            self,
            method,
            url,
            params=None,
            data=None,
            headers=None,
            cookies=None,
            files=None,
            auth=None,
            timeout=None,
            allow_redirects=True,
            proxies=None,
            hooks=None,
            stream=None,
            verify=None,
            cert=None,
            json=None,
            zyte_policies=None,
            # Do not change policy on redirects
            fixed_policies=False
    ):
        req = Request(
            method=method.upper(),
            url=url,
            headers=headers,
            files=files,
            data=data or {},
            json=json,
            params=params or {},
            auth=auth,
            cookies=cookies,
            hooks=hooks,
        )
        prep = self.prepare_request(req)

        proxies = proxies or {}

        settings = self.merge_environment_settings(
            prep.url, proxies, stream, verify, cert
        )

        # Send the request.
        send_kwargs = {
            'timeout': timeout,
            'allow_redirects': allow_redirects,
            'zyte_policies': zyte_policies,
            'fixed_policies': fixed_policies
        }
        send_kwargs.update(settings)
        resp = self.send(prep, **send_kwargs)

        return resp

    def _req_policies(self, req: PreparedRequest):
        zyte_policies = self.policies if self.policies else get_matching_policies(
            url=req.url)
        return zyte_policies + self.fallback_policies if zyte_policies else self.fallback_policies

    def send(
            self,
            request,
            *args,
            zyte_policies: List[ZytePolicy] = None,
            fixed_policies: bool = False,
            **kwargs,
    ):
        if not isinstance(zyte_policies, list) and zyte_policies is not None:
            zyte_policies = [zyte_policies]
        if not zyte_policies:
            zyte_policies = self._req_policies(request)
        kwargs['allow_redirects'] = False
        r = self._send_with_policies(request,
                                     zyte_policies,
                                     *args, **kwargs)
        while r.is_redirect:
            url = self.get_redirect_target(r)
            req = r.request.copy()
            req.url = url
            if not fixed_policies and not self.policies:
                zyte_policies = self._req_policies(req)
            r = self._send_with_policies(req,
                                         zyte_policies,
                                         *args,
                                         **kwargs)
        return r

    def _send_with_policy(self, request: PreparedRequest,
                          zyte_policy: ZytePolicy, *args, **kwargs):
        r = None
        retry = self.retry.copy(
            before=make_before_cb(request.url, zyte_policy, self.logger),
            after=make_after_cb(request.url, self.logger),
            stop=stop_after_attempt(
                1) if zyte_policy == BYPASS_POLICY else self.retry.stop)
        for atp in retry:
            with atp:
                r = zyte_policy.sender(self)(request, *args, **kwargs)
                r.raise_for_status()
                if is_bad_landing_page(r.content):
                    raise BadLandingPageException(
                        f'Bad landing page with URL - {r.url}')
                return r
        return r

    @staticmethod
    def _modify_response_for_redirect(resp: Response):
        for redirector in ALL_REDIRECTORS:
            if target := redirector(resp):
                resp.headers.update({'location': target})
                resp.status_code = 302
                return resp
        return resp

    def _send_with_policies(self, request: PreparedRequest,
                            zyte_policies: List[ZytePolicy], *args, **kwargs):
        r = None
        exc = None
        for p in zyte_policies:
            try:
                r = self._send_with_policy(request, p, *args, **kwargs)
                break
            except Exception as e:
                exc = e
        if r is None:
            raise exc
        if is_pdf(r.content):
            return r
        return self._modify_response_for_redirect(r)


if __name__ == '__main__':
    print(
        get_matching_policies('https://www.nejm.org/doi/10.1056/NEJMoa2034577'))
