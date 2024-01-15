import logging
import os
import re
from base64 import standard_b64decode
from threading import current_thread
from typing import List

import requests
from requests import Request, PreparedRequest, Response
from sqlalchemy import Column, String, JSON, Enum, Integer
from tenacity import Retrying, stop_after_attempt, wait_exponential

from app import db
from const import ZYTE_API_URL, ZYTE_API_KEY
from pdf_util import is_pdf
from redirectors import ALL_REDIRECTORS
from util import is_bad_landing_page

CRAWLERA_PROXY = 'http://{}:DUMMY@impactstory.crawlera.com:8010'.format(
    os.getenv("CRAWLERA_KEY"))

_DEFAULT_ZYTE_PARAMS = {"httpResponseBody": True, "httpResponseHeaders": True}


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
    return response


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
    priority = Column(Integer, nullable=False, default=1)

    def __str__(self):
        return f'<ZytePolicy id={self.id} type={self.type} regex={self.regex} profile={self.profile} priority={self.priority}>'

    def __repr__(self):
        return self.__str__()

    def match(self, doi_or_domain):
        return bool(re.search(self.regex, doi_or_domain))

    @classmethod
    def get_matching_policies(cls, url=None, doi=None):
        if url is None and doi is None:
            raise ValueError('URL and DOI parameters cannot both be None')
        policies = []
        for policy in _ALL_POLICIES:
            if url and policy.type == 'url' and policy.match(url):
                policies.append(policy)
            elif doi and policy.type == 'doi' and policy.match(doi):
                policies.append(policy)
        return sorted(policies, key=lambda p: p.priority, reverse=False)

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
DEFAULT_FALLBACK_POLICIES = [ZytePolicy(profile='proxy', priority=1),
                             ZytePolicy(profile='api', priority=2)]
BYPASS_POLICY = ZytePolicy(profile='bypass')


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
                                        reverse=False) if fallback_policies else []
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
            zyte_policies = self.policies if self.policies else ZytePolicy.get_matching_policies(
                url=request.url)
            if not zyte_policies:
                zyte_policies = [BYPASS_POLICY]
        kwargs['allow_redirects'] = False
        r = self._send_with_policies(request,
                                     zyte_policies + self.fallback_policies,
                                     *args, **kwargs)
        while r.is_redirect:
            url = self.get_redirect_target(r)
            req = r.request.copy()
            req.url = url
            if not fixed_policies:
                zyte_policies = ZytePolicy.get_matching_policies(
                    url=req.url) or [BYPASS_POLICY]
            r = self._send_with_policies(req,
                                         zyte_policies + self.fallback_policies,
                                         *args,
                                         **kwargs)
        return r

    def _send_with_policy(self, request: PreparedRequest,
                          zyte_policy: ZytePolicy, *args, **kwargs):
        r = None
        retry = self.retry.copy(
            before=make_before_cb(request.url, zyte_policy, self.logger),
            after=make_after_cb(request.url, self.logger))
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
            except Exception as e:
                exc = e
        if r is None:
            raise exc
        if is_pdf(r.content):
            return r
        return self._modify_response_for_redirect(r)


if __name__ == '__main__':
    s = ZyteSession()
    url = 'https://doi.org/10.1086/109234'
    # policy = ZytePolicy.query.get()
    # policy = ZytePolicy.get_matching_policies(url=url)[0]
    # policy = ZytePolicy(type='url', regex='10\.1016/j\.physletb',
    #                     profile='proxy')
    r = s.get(url)
    print(r.text)
