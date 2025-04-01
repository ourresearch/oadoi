from base64 import b64decode
import os
import re
from dataclasses import dataclass
from time import sleep
from time import time
from typing import Optional
import json

import certifi
import requests
import tenacity

from app import logger
from tenacity import retry, stop_after_attempt, wait_exponential, \
    retry_if_result
import requests.exceptions
from util import elapsed
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

    return session_id


def chooser_redirect(r):
    """
    Check if the response contains a "Chooser" title and extract redirect links.

    This function works with ResponseObject instances returned by Zyte API.
    """
    # Get the content as text
    try:
        content = r.text_small() if hasattr(r, 'text_small') else r.content

        # If content is bytes, decode it
        if isinstance(content, bytes):
            content = content.decode('utf-8', 'ignore')

        # Look for the Chooser title
        if '<title>Chooser</title>' in content:
            # Find resource links
            links = re.findall(
                r'<div class="resource-line">.*?<a\s+href="(.*?)".*?</div>',
                content, re.DOTALL
            )

            if links:
                logger.info(f'Found chooser redirect to: {links[0]}')
                return links[0]
    except Exception as e:
        logger.error(f"Error in chooser_redirect: {str(e)}")

    return None


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
def call_requests_get(url=None, headers=None, read_timeout=300, connect_timeout=300,
                      stream=False, publisher=None, session_id=None, ask_slowly=False,
                      verify=False, cookies=None, redirected_url=None, attempt_n=0):
    if redirected_url:
        url = redirected_url

    # default parameters setup
    # default parameters setup
    default_params = {
        "url": url,
        "httpResponseBody": True,
        "httpResponseHeaders": True,
    }

    # get policies if they exist
    matching_policies = get_matching_policies(url)
    if matching_policies:
        policy = matching_policies[min(attempt_n, len(matching_policies) - 1)]

        if policy.profile == 'api' and policy.params is not None:
            logger.info(f'Using Zyte API profile for url: {url}')
            zyte_params = policy.params
        else:
            logger.info(f'Using Zyte profile with proxy mode for url: {url}')
            zyte_params = default_params
    else:
        logger.info(f'No matching policies - using default Zyte profile for url: {url}')
        zyte_params = default_params

    if zyte_params is None:
        logger.warning(f"zyte_params was None for url: {url}, using default params")
        zyte_params = default_params.copy()

    # set URL in parameters
    zyte_params["url"] = url

    # make the API call
    zyte_api_response = call_with_zyte_api(url, zyte_params)
    good_status_code = zyte_api_response.get('statusCode')
    bad_status_code = zyte_api_response.get('status')

    if good_status_code is not None and good_status_code < 400:
        logger.info(f"zyte api good status code for {url}: {good_status_code}")

        headers = zyte_api_response.get('httpResponseHeaders', [])
        logger.info(f"headers: {headers}")

        content = None
        if 'httpResponseBody' in zyte_api_response:
            content = b64decode(zyte_api_response.get('httpResponseBody'))
        elif 'browserHtml' in zyte_api_response:
            content = zyte_api_response.get('browserHtml').encode()
        else:
            content = b''

        # create response object
        r = ResponseObject(
            content=content,
            headers=headers,
            status_code=good_status_code,
            url=zyte_api_response.get('url', url),
        )

        content_type = r.headers.get("Content-Type", "").lower()
        is_pdf = "application/pdf" in content_type

        # try to detect PDF signature in content
        if not is_pdf and isinstance(r.content, bytes) and len(r.content) > 4:
            is_pdf = r.content.startswith(b'%PDF-')

        if not is_pdf and isinstance(r.content, bytes):
            try:
                r.content = r.content.decode('utf-8', 'ignore')
            except (UnicodeDecodeError, AttributeError):
                # Keep as binary if decoding fails
                pass

        # check for doi.org chooser redirects
        redirect_url = chooser_redirect(r)
        if redirect_url:
            logger.info(f"Following chooser redirect to {redirect_url}")

            # recursively follow the redirect with a new request
            return call_requests_get(
                url=redirect_url,
                headers=headers,
                read_timeout=read_timeout,
                connect_timeout=connect_timeout,
                stream=stream,
                publisher=publisher,
                session_id=session_id,
                ask_slowly=ask_slowly,
                verify=verify,
                cookies=cookies,
                attempt_n=attempt_n
            )

        return r
    else:
        # Create a response for error cases
        r = ResponseObject(
            content='',
            headers=[],
            status_code=bad_status_code,
            url=url,
        )
        logger.info(f"zyte api bad status code for {url}: {bad_status_code}")
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
    r = http_get('https://doi.org/10.1002/jum.15761')
    print(r.status_code)
