from base64 import b64decode
import html
import inspect
import os
import re
from dataclasses import dataclass
from time import sleep
from time import time
from typing import Optional
from urllib.parse import urljoin, urlparse
import json

import certifi
import requests
import tenacity

from app import logger, db
from tenacity import retry, stop_after_attempt, wait_exponential, \
    retry_if_result
import requests.exceptions
from sqlalchemy import sql
from util import DelayedAdapter
from util import elapsed
from util import get_link_target
from util import is_same_publisher
from zyte_session import get_matching_policies

MAX_PAYLOAD_SIZE_BYTES = 1000 * 1000 * 10  # 10mb

os.environ['NO_PROXY'] = 'impactstory.crawlera.com'


@dataclass
class ResponseObject:
    content: bytes
    headers: dict
    status_code: int
    url: str
    cookies: Optional[str] = None

    def __post_init__(self):
        self.headers = {header['name']: header['value'] for header in
                        self.headers}

    def text_small(self):
        return self.content

    def text_big(self):
        return self.content

    def content_big(self):
        return self.content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f'Bad status code for URL {self.url}: {self.status_code}')


def _create_cert_bundle():
    crt_file = 'data/custom-certs.crt'

    with open(crt_file, 'w') as combined_certs:
        for source in [certifi.where(), 'data/crawlera-ca.crt']:
            with open(source, 'r') as s:
                for line in s:
                    combined_certs.write(line)

    return crt_file


_cert_bundle = _create_cert_bundle()


def is_response_too_large(r):
    if not "Content-Length" in r.headers:
        # logger.info(u"can't tell if page is too large, no Content-Length header {}".format(r.url))
        return False

    content_length = r.headers["Content-Length"]
    # if is bigger than 25 MB, don't keep it don't parse it, act like we couldn't get it
    # if doing 100 in parallel, this would be 100MB, which fits within 512MB dyno limit
    if int(content_length) >= (25 * 1000 * 1000):
        logger.info("Content Too Large on GET on {url}".format(url=r.url))
        return True
    return False


def get_session_id():
    # set up proxy
    session_id = None

    while not session_id:
        crawlera_username = os.getenv("CRAWLERA_KEY")
        r = requests.post("http://impactstory.crawlera.com:8010/sessions",
                          auth=(crawlera_username, 'DUMMY'),
                          proxies={'http': None, 'https': None})
        if r.status_code == 200:
            session_id = r.headers["X-Crawlera-Session"]
        else:
            # bad call.  sleep and try again.
            sleep(1)

    # logger.info(u"done with get_session_id. Got sessionid {}".format(session_id))

    return session_id


def _log_oup_redirect(user_agent, requested_url, redirect_url):
    db.engine.execute(
        sql.text(
            'insert into oup_captcha_redirects (time, user_agent, requested_url, redirect_url) values(now(), :user_agent, :request_url, :redirect_url)').bindparams(
            user_agent=user_agent,
            request_url=requested_url,
            redirect_url=redirect_url
        )
    )


def chooser_redirect(r):
    if '<title>Chooser</title>' in r.text_small():
        if links := re.findall(
                r'<div class="resource-line">.*?<a\s+href="(.*?)".*?</div>',
                r.text_small(), re.DOTALL):
            return links[0]
    return None


def keep_redirecting(r, publisher):
    # don't read r.content unless we have to, because it will cause us to download the whole thig instead of just the headers

    if target := chooser_redirect(r):
        logger.info('Chooser redirect: {}'.format(target))
        return target

    if r.is_redirect:
        location = r.headers.get('location', '')
        location = location if location.startswith('http') else urljoin(r.url,
                                                                        location)
        location = location.replace('http:///', 'http://').replace('https:///',
                                                                   'https://')
        logger.info('30x redirect: {}'.format(location))

        if location.startswith(
                'https://academic.oup.com/crawlprevention/governor') or re.match(
            r'https?://academic\.oup\.com/.*\.pdf', r.url):
            _log_oup_redirect(r.headers.get('X-Crawlera-Debug-UA'), r.url,
                              location)

        return location

    # 10.5762/kais.2016.17.5.316
    if "content-length" in r.headers:
        # manually follow javascript if that's all that's in the payload
        file_size = int(r.headers["content-length"])
        if file_size < 500:
            matches = re.findall(r"<script>location.href='(.*)'</script>",
                                 r.text_small(), re.IGNORECASE)
            if matches:
                redirect_url = matches[0]
                if redirect_url.startswith("/"):
                    redirect_url = get_link_target(redirect_url, r.url)
                return redirect_url

    # 10.1097/00003643-201406001-00238
    if publisher and is_same_publisher(publisher,
                                       "Ovid Technologies (Wolters Kluwer Health)"):
        matches = re.findall(r"OvidAN = '(.*?)';", r.text_small(),
                             re.IGNORECASE)
        if matches:
            an_number = matches[0]
            redirect_url = "http://content.wkhealth.com/linkback/openurl?an={}".format(
                an_number)
            return redirect_url

    # 10.1097/01.xps.0000491010.82675.1c
    hostname = urlparse(r.url).hostname
    if hostname and hostname.endswith('ovid.com'):
        matches = re.findall(r'var journalURL = "(.*?)";', r.text_small(),
                             re.IGNORECASE)
        if matches:
            journal_url = matches[0]
            logger.info(
                'ovid journal match. redirecting to {}'.format(journal_url))
            return journal_url

    # handle meta redirects
    redirect_re = re.compile('<meta[^>]*http-equiv="?refresh"?[^>]*>',
                             re.IGNORECASE | re.DOTALL)
    redirect_match = redirect_re.findall(r.text_small())
    if redirect_match:
        redirect = redirect_match[0]
        logger.info('found a meta refresh element: {}'.format(redirect))
        url_re = re.compile('url=["\']?([^">\']*)', re.IGNORECASE | re.DOTALL)
        url_match = url_re.findall(redirect)

        if url_match:
            redirect_path = html.unescape(url_match[0].strip())
            redirect_url = urljoin(r.request.url, redirect_path)
            if not redirect_url.endswith(
                    'Error/JavaScript.html') and not redirect_url.endswith(
                '/?reason=expired'):
                logger.info(
                    "redirect_match! redirecting to {}".format(redirect_url))
                return redirect_url

    redirect_re = re.compile(
        r"window\.location\.replace\('(https://pdf\.sciencedirectassets\.com[^']*)'\)")
    redirect_match = redirect_re.findall(r.text_small())
    if redirect_match:
        redirect_url = redirect_match[0]
        logger.info(
            "javascript redirect_match! redirecting to {}".format(redirect_url))
        return redirect_url

    return None


class RequestWithFileDownload(object):

    def content_small(self):
        return self.content_big()

        # if hasattr(self, "content_read"):
        #     return self.content_read
        #
        # self.content_read = self.content
        # return self.content_read

    def content_big(self):
        if hasattr(self, "content_read"):
            return self.content_read

        if not self.raw:
            self.content_read = self.content
            return self.content_read

        megabyte = 1024 * 1024
        maxsize = 25 * megabyte

        self.content_read = b""
        for chunk in self.iter_content(megabyte):
            self.content_read += chunk
            if len(self.content_read) > maxsize:
                logger.info(
                    "webpage is too big at {}, only getting first {} bytes".format(
                        self.request.url, maxsize))
                self.close()
                return self.content_read
        return self.content_read

    def _text_encoding(self):
        if not self.encoding or self.encoding == 'binary':
            return 'utf-8'

        return self.encoding

    def text_small(self):
        return str(self.content_small(), encoding=self._text_encoding(),
                   errors="ignore")

    def text_big(self):
        return str(self.content_big(),
                   encoding=self._text_encoding() or "utf-8", errors="ignore")


def request_ua_headers():
    return {
        'User-Agent': 'Unpaywall (http://unpaywall.org/; mailto:team@impactstory.org)',
        'From': 'team@impactstory.org',
    }


def before_retry(retry_state):
    redirected_url = retry_state.outcome.result().url
    logger.info(f"retrying due to {retry_state.outcome.result().status_code}")
    retry_state.kwargs['redirected_url'] = redirected_url
    retry_state.kwargs['attempt_n'] = retry_state.attempt_number


def is_retry_status(response):
    return response.status_code in {429, 500, 502, 503, 504, 520, 403}


@retry(stop=stop_after_attempt(2),
       wait=wait_exponential(multiplier=1, min=4, max=10),
       retry=retry_if_result(is_retry_status),
       before_sleep=before_retry)
def call_requests_get(url=None,
                      headers=None,
                      read_timeout=300,
                      connect_timeout=300,
                      stream=False,
                      publisher=None,
                      session_id=None,
                      ask_slowly=False,
                      verify=False,
                      cookies=None,
                      use_zyte_api_profile=False,
                      redirected_url=None,
                      attempt_n=0,
                      logger=logger):
    if redirected_url:
        url = redirected_url

    headers = headers or {}

    saved_http_proxy = os.getenv("HTTP_PROXY", "")
    saved_https_proxy = os.getenv("HTTPS_PROXY", "")

    if ask_slowly:
        logger.info(f"asking slowly for url: {url}")

        crawlera_url = 'http://{}:DUMMY@impactstory.crawlera.com:8010'.format(
            os.getenv("CRAWLERA_KEY"))

        os.environ["HTTP_PROXY"] = crawlera_url
        os.environ["HTTPS_PROXY"] = crawlera_url

        if session_id:
            headers["X-Crawlera-Session"] = session_id

        headers["X-Crawlera-Debug"] = "ua,request-time"
        headers["X-Crawlera-Timeout"] = "{}".format(
            300 * 1000)  # tomas recommended 300 seconds in email

        read_timeout = 600
        connect_timeout = 600
    else:
        if 'User-Agent' not in headers:
            headers['User-Agent'] = request_ua_headers()['User-Agent']

        if 'From' not in headers:
            headers['From'] = request_ua_headers()['From']

    following_redirects = True
    num_browser_redirects = 0
    num_http_redirects = 0

    requests_session = requests.Session()

    use_crawlera_profile = False
    zyte_params = None

    while following_redirects:

        if policies := get_matching_policies(url):
            policy = policies[min(attempt_n, len(policies) - 1)]
            if policy.profile == 'api':
                logger.info(f'using zyte profile for url: {url}')
                use_zyte_api_profile = True
                zyte_params = policy.params
            elif policy.profile == 'proxy':
                logger.info(f'using crawlera profile for url: {url}')
                use_crawlera_profile = True

        if use_crawlera_profile:
            headers["X-Crawlera-Profile"] = "desktop"
            headers["X-Crawlera-Cookies"] = "disable"
            headers.pop("User-Agent", None)
            headers.pop("X-Crawlera-Profile-Pass", None)
        else:
            headers["X-Crawlera-Cookies"] = "disable"
            headers["Accept-Language"] = 'en-US,en;q=0.9'
            if headers.get("User-Agent"):
                headers["X-Crawlera-UA"] = "pass"

        requests_session.mount('http://', DelayedAdapter())
        requests_session.mount('https://', DelayedAdapter())

        if "citeseerx.ist.psu.edu/" in url:
            url = url.replace("http://", "https://")
            proxy_url = os.getenv("STATIC_IP_PROXY")
            proxies = {"https": proxy_url, "http": proxy_url}
        else:
            proxies = {}

        if use_zyte_api_profile:
            zyte_api_response = call_with_zyte_api(url, zyte_params)
            good_status_code = zyte_api_response.get('statusCode')
            bad__status_code = zyte_api_response.get('status')
            if good_status_code is not None and good_status_code < 400:
                logger.info(
                    f"zyte api good status code for {url}: {good_status_code}")
                # make mock requests response object
                r = ResponseObject(
                    content=b64decode(
                        zyte_api_response.get(
                            'httpResponseBody')) if 'httpResponseBody' in
                                                    zyte_api_response else zyte_api_response.get(
                        'browserHtml').encode(),
                    headers=zyte_api_response.get('httpResponseHeaders'),
                    status_code=zyte_api_response.get('statusCode'),
                    url=zyte_api_response.get('url'),
                )
                if r.headers.get("Content-Type") != "application/pdf":
                    r.content = r.content.decode('utf-8', 'ignore')
                return r
            else:
                r = ResponseObject(
                    content='',
                    headers={},
                    status_code=bad__status_code,
                    url=url,
                )
                logger.info(
                    f"zyte api bad status code for {url}: {bad__status_code}")
                return r
        else:
            # logger.info(u"getting url {}".format(url))
            r = requests_session.get(url,
                                     headers=headers,
                                     timeout=(connect_timeout, read_timeout),
                                     stream=stream,
                                     proxies=proxies,
                                     allow_redirects=False,
                                     verify=(verify and _cert_bundle),
                                     cookies=cookies)

            # trigger 503 for iop.org pdf urls, so that we retry with zyte api
            if 'iop.org' in url and url.endswith('/pdf'):
                r.status_code = 503

        # from http://jakeaustwick.me/extending-the-requests-response-class/
        for method_name, method in inspect.getmembers(RequestWithFileDownload,
                                                      inspect.isfunction):
            setattr(requests.models.Response, method_name, method)

        if r and not r.encoding:
            r.encoding = "utf-8"

        # check to see if we actually want to keep redirecting, using business-logic redirect paths
        following_redirects = False
        if (r.is_redirect and num_http_redirects < 15) or (
                r.status_code == 200 and num_browser_redirects < 5):
            if r.is_redirect:
                num_http_redirects += 1
            if r.status_code == 200:
                num_browser_redirects += 1

            redirect_url = keep_redirecting(r, publisher)
            if redirect_url:
                if "hcvalidate.perfdrive.com" in redirect_url:
                    # do not follow this redirect with proxy
                    r.status_code = 503
                    return r
                else:
                    following_redirects = True
                    url = redirect_url

        if ask_slowly and not use_zyte_api_profile and not use_crawlera_profile and headers.get(
                "User-Agent"):
            crawlera_ua = r.headers.get("X-Crawlera-Debug-UA")
            if crawlera_ua:
                logger.info('set proxy UA: {}'.format(crawlera_ua))
                headers["User-Agent"] = crawlera_ua
                headers["X-Crawlera-UA"] = "pass"

    # now set proxy situation back to normal
    os.environ["HTTP_PROXY"] = saved_http_proxy
    os.environ["HTTPS_PROXY"] = saved_http_proxy

    return r


def http_get(url,
             headers=None,
             read_timeout=60,
             connect_timeout=60,
             stream=False,
             cache_enabled=False,
             allow_redirects=True,
             publisher=None,
             session_id=None,
             ask_slowly=False,
             verify=False,
             cookies=None):
    headers = headers or {}

    start_time = time()

    # reset
    os.environ["HTTP_PROXY"] = ""

    try:
        logger.info("LIVE GET on {}".format(url))
    except UnicodeDecodeError:
        logger.info("LIVE GET on an url that throws UnicodeDecodeError")

    try:
        r = call_requests_get(url,
                              headers=headers,
                              read_timeout=read_timeout,
                              connect_timeout=connect_timeout,
                              stream=stream,
                              publisher=publisher,
                              session_id=session_id,
                              ask_slowly=ask_slowly,
                              verify=verify,
                              cookies=cookies)
    except tenacity.RetryError:
        logger.info(f"tried too many times for {url}")
        raise
    logger.info("finished http_get for {} in {} seconds".format(url, elapsed(
        start_time, 2)))
    return r


def call_with_zyte_api(url, params=None):
    zyte_api_url = "https://api.zyte.com/v1/extract"
    zyte_api_key = os.getenv("ZYTE_API_KEY")
    default_params = {
        "url": url,
        "httpResponseHeaders": True,
        "httpResponseBody": True,
        "requestHeaders": {"referer": "https://www.google.com/"},
    }
    if not params:
        params = default_params
    params['url'] = url
    os.environ["HTTP_PROXY"] = ''
    os.environ["HTTPS_PROXY"] = ''

    logger.info(f"calling zyte api for {url}")
    if "wiley.com" in url:
        # get cookies
        cookies_response = requests.post(zyte_api_url, auth=(zyte_api_key, ''),
                                         json={
                                             "url": url,
                                             "browserHtml": True,
                                             "javascript": True,
                                             "experimental": {
                                                 "responseCookies": True
                                             }
                                         }, verify=False)
        cookies_response = json.loads(cookies_response.text)
        cookies = cookies_response.get("experimental", {}).get(
            "responseCookies", {})

        # use cookies to get valid response
        if cookies:
            response = requests.post(zyte_api_url, auth=(zyte_api_key, ''),
                                     json={
                                         "url": url,
                                         "httpResponseHeaders": True,
                                         "httpResponseBody": True,
                                         "experimental": {
                                             "requestCookies": cookies
                                         }
                                     }, verify=False)
        else:
            response = requests.post(zyte_api_url, auth=(zyte_api_key, ''),
                                     json={
                                         "url": url,
                                         "httpResponseHeaders": True,
                                         "httpResponseBody": True,
                                         "requestHeaders": {
                                             "referer": "https://www.google.com/"},
                                     }, verify=False)
    else:
        response = requests.post(zyte_api_url, auth=(zyte_api_key, ''),
                                 json=params, verify=False)
    return response.json()


def get_cookies_with_zyte_api(url):
    zyte_api_url = "https://api.zyte.com/v1/extract"
    zyte_api_key = os.getenv("ZYTE_API_KEY")
    cookies_response = requests.post(zyte_api_url, auth=(zyte_api_key, ''),
                                     json={
                                         "url": url,
                                         "browserHtml": True,
                                         "javascript": True,
                                         "experimental": {
                                             "responseCookies": True
                                         }
                                     })
    cookies_response = json.loads(cookies_response.text)
    cookies = cookies_response.get("experimental", {}).get("responseCookies",
                                                           {})
    return cookies


if __name__ == '__main__':
    # r = http_get('https://doi.org/10.1088/1475-7516/2010/04/014')
    # print(r.status_code)
    r = http_get('https://doi.org/10.1002/jum.15761')
    print(r.status_code)
