import os
import sys
import re
import hashlib
import json
import requests
import socket
import boto
import requests
import shutil
import urlparse
from requests.auth import HTTPProxyAuth
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from time import time
from time import sleep
import inspect

from app import logger
from util import clean_doi
from util import get_tree
from util import get_link_target
from util import elapsed
from util import NoDoiException
from util import DelayedAdapter

MAX_PAYLOAD_SIZE_BYTES = 1000*1000*10 # 10mb

def is_response_too_large(r):
    if not "Content-Length" in r.headers:
        # logger.info(u"can't tell if page is too large, no Content-Length header {}".format(r.url))
        return False

    content_length = r.headers["Content-Length"]
    # if is bigger than 25 MB, don't keep it don't parse it, act like we couldn't get it
    # if doing 100 in parallel, this would be 100MB, which fits within 512MB dyno limit
    if int(content_length) >= (25 * 1000 * 1000):
        logger.info(u"Content Too Large on GET on {url}".format(url=r.url))
        return True
    return False

# 10.2514/6.2006-5946!  https://arc.aiaa.org/doi/pdf/10.2514/6.2006-5946
# 10.3410/f.6269956.7654055 none
# 10.2514/6.2006-2106 none  (lots of redirects)
# 10.5040/9780567662088.part-003 none (book)
# 10.1016/j.jvcir.2016.03.027 (elsevier, relative links)
# 10.1002/(sici)1096-911x(200006)34:6<432::aid-mpo10>3.0.co;2-1 (has a blank tdm_api)
# python update.py Crossref.run_with_hybrid --id=10.2514/6.2006-5946


def get_session_id():
    # set up proxy
    session_id = None
    while not session_id:
        crawlera_username = os.getenv("CRAWLERA_KEY")
        r = requests.post("http://impactstory.crawlera.com:8010/sessions", auth=(crawlera_username, 'DUMMY'))
        if r.status_code == 200:
            session_id = r.headers["X-Crawlera-Session"]
        else:
            # bad call.  sleep and try again.
            sleep(1)

    # logger.info(u"done with get_session_id. Got sessionid {}".format(session_id))

    return session_id


def keep_redirecting(r, my_pub):
    # don't read r.content unless we have to, because it will cause us to download the whole thig instead of just the headers

    # 10.5762/kais.2016.17.5.316
    if ("content-length" in r.headers):
        # manually follow javascript if that's all that's in the payload
        file_size = int(r.headers["content-length"])
        if file_size < 500:
            matches = re.findall(ur"<script>location.href='(.*)'</script>", r.content_small(), re.IGNORECASE)
            if matches:
                redirect_url = matches[0]
                if redirect_url.startswith(u"/"):
                    redirect_url = get_link_target(redirect_url, r.url)
                return redirect_url

    # 10.1097/00003643-201406001-00238
    if my_pub and my_pub.is_same_publisher("Ovid Technologies (Wolters Kluwer Health)"):
        matches = re.findall(ur"OvidAN = '(.*?)';", r.content_small(), re.IGNORECASE)
        if matches:
            an_number = matches[0]
            redirect_url = "http://content.wkhealth.com/linkback/openurl?an={}".format(an_number)
            return redirect_url

    # handle meta redirects
    # redirect_re = re.compile('<meta[^>]*?url=["\'](.*?)["\']', re.IGNORECASE)
    # redirect_match = redirect_re.findall(r.content_small())
    # if redirect_match:
    #     redirect_url = urlparse.urljoin(r.request.url, redirect_match[0].strip())
    #     logger.info(u"redirect_match! redirecting to {}".format(redirect_url))
    #     return redirect_url

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

        megabyte = 1024*1024
        maxsize = 25 * megabyte
        self.content_read = b""
        for chunk in self.iter_content(megabyte):
            self.content_read += chunk
            if len(self.content_read) > maxsize:
                logger.info(u"webpage is too big at {}, only getting first {} bytes".format(self.request.url, maxsize))
                self.close()
                return self.content_read
        return self.content_read


def call_requests_get(url,
                      headers={},
                      read_timeout=60,
                      connect_timeout=60,
                      stream=False,
                      related_pub=None,
                      ask_slowly=False):

    # if u"doi.org/" in url:
    #     url = get_crossref_resolve_url(url, related_pub)
    #     if not url:
    #         raise NoDoiException
    #     logger.info(u"new url is {}".format(url))

    saved_http_proxy = os.getenv("HTTP_PROXY", "")
    saved_https_proxy = os.getenv("HTTPS_PROXY", "")

    if ask_slowly:
        logger.info(u"asking slowly")
        crawlera_url = 'http://{}:DUMMY@impactstory.crawlera.com:8010'.format(os.getenv("CRAWLERA_KEY"))
        os.environ["HTTP_PROXY"] = crawlera_url
        os.environ["HTTPS_PROXY"] = crawlera_url

        session_id = None
        if related_pub:
            if hasattr(related_pub, "session_id") and related_pub.session_id:
                session_id = related_pub.session_id

        headers["X-Crawlera-Session"] = session_id
        headers["X-Crawlera-Debug"] = "ua,request-time"

        # headers["X-Crawlera-UA"] = "pass"
        headers["X-Crawlera-Timeout"] = "{}".format(300 * 1000)  # tomas recommended 300 seconds in email
    else:
        headers["From"] = "team@impactstory.org"

    following_redirects = True
    num_redirects = 0
    while following_redirects:
        requests_session = requests.Session()

        if ask_slowly:
            retries = Retry(total=1,
                            backoff_factor=0.1,
                            status_forcelist=[500, 502, 503, 504])
        else:
            retries = Retry(total=0,
                            backoff_factor=0.1,
                            status_forcelist=[500, 502, 503, 504])
        requests_session.mount('http://', DelayedAdapter(max_retries=retries))
        requests_session.mount('https://', DelayedAdapter(max_retries=retries))

        if u"citeseerx.ist.psu.edu/" in url:
            url = url.replace("http://", "https://")
            proxy_url = os.getenv("STATIC_IP_PROXY")
            proxies = {"https": proxy_url, "http": proxy_url}
        else:
            proxies = {}

        # logger.info(u"getting url {}".format(url))
        r = requests_session.get(url,
                    headers=headers,
                    timeout=(connect_timeout, read_timeout),
                    stream=stream,
                    proxies=proxies,
                    allow_redirects=True,
                    verify=False)


        # from http://jakeaustwick.me/extending-the-requests-response-class/
        for method_name, method in inspect.getmembers(RequestWithFileDownload, inspect.ismethod):
            setattr(requests.models.Response, method_name, method.im_func)

        if r and not r.encoding:
            r.encoding = "utf-8"

        # check to see if we actually want to keep redirecting, using business-logic redirect paths
        following_redirects = False
        num_redirects += 1
        if (r.status_code == 200) and (num_redirects < 5):
            redirect_url = keep_redirecting(r, related_pub)
            if redirect_url:
                following_redirects = True
                url = redirect_url

    # now set proxy situation back to normal
    os.environ["HTTP_PROXY"] = saved_http_proxy
    os.environ["HTTPS_PROXY"] = saved_http_proxy

    return r


def http_get(url,
             headers={},
             read_timeout=60,
             connect_timeout=60,
             stream=False,
             cache_enabled=False,
             allow_redirects=True,
             related_pub=None,
             ask_slowly=False):

    start_time = time()

    # reset
    os.environ["HTTP_PROXY"] = ""

    try:
        logger.info(u"LIVE GET on {}".format(url))
    except UnicodeDecodeError:
        logger.info(u"LIVE GET on an url that throws UnicodeDecodeError")

    max_tries = 2
    if ask_slowly:
        max_tries = 3
    success = False
    tries = 0
    r = None
    while not success:
        try:
            r = call_requests_get(url,
                                  headers=headers,
                                  read_timeout=read_timeout,
                                  connect_timeout=connect_timeout,
                                  stream=stream,
                                  related_pub=related_pub,
                                  ask_slowly=ask_slowly)
            success = True
        except (KeyboardInterrupt, SystemError, SystemExit):
            raise
        except Exception as e:
            # don't make this an exception log for now
            logger.info(u"exception in call_requests_get")
            tries += 1
            if tries >= max_tries:
                logger.info(u"in http_get, tried too many times, giving up")
                raise
            else:
                logger.info(u"in http_get, got an exception, trying again")
        finally:
            logger.info(u"finished http_get for {} in {} seconds".format(url, elapsed(start_time, 2)))

    return r
