import os
import sys
import re
import hashlib
import json
import requests
import socket
import boto
import requests
from requests.auth import HTTPProxyAuth
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from time import time
from time import sleep

from app import requests_cache_bucket
from app import logger
from util import clean_doi
from util import get_tree
from util import get_link_target
from util import elapsed
from util import NoDoiException
from util import DelayedAdapter

MAX_PAYLOAD_SIZE_BYTES = 1000*1000*10 # 10mb
CACHE_FOLDER_NAME = "tng-requests-cache"

class CachedResponse:
    def __init__(self, **kwargs):
        self.headers = {}
        self.status_code = 200
        for (k, v) in kwargs.iteritems():
            setattr(self, k, v)

    @property
    def content(self):
        return self.file_contents

    @property
    def text(self):
        return self.file_contents

    # allows it to be treated the same way as a streaming response object
    def close(self):
        pass


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

def get_resolve_url_from_doi_url(doi, connect_timeout, read_timeout):
    r = requests.get("http://doi.org/{}".format(doi),
                    allow_redirects=False,
                    timeout=(connect_timeout, read_timeout))
    # logger.info(u"new responses")
    # logger.info(u"r.status_code: {}".format(r.status_code))
    # logger.info(u"r.headers: {}".format(r.headers))
    try:
        response_url = r.headers["Location"]
    except KeyError:
        raise NoDoiException
    return response_url


def get_crossref_resolve_url(url, related_pub=None):
    doi = clean_doi(url)
    connect_timeout = 600
    read_timeout = 600
    r = None

    if related_pub and related_pub.tdm_api:
        page = related_pub.tdm_api.encode("utf-8")
        # logger.info(u"got doi tdm page from db")
    else:
        logger.info(u"didn't find doi tdm page in db")
        # reset this in case it had been set
        os.environ["HTTP_PROXY"] = ""

        headers = {"Accept": "application/vnd.crossref.unixsd+xml"}
        headers["User-Agent"] = "oaDOI.org"
        headers["From"] = "team@impactstory.org"

        url = url.replace("http://", "https://")
        proxy_url = os.getenv("STATIC_IP_PROXY")
        static_ip_proxies = {"https": proxy_url, "http": proxy_url}
        r = requests.get(url,
                         headers=headers,
                         proxies=static_ip_proxies,
                         timeout=(connect_timeout, read_timeout),
                         allow_redirects=True,
                         verify=False
                         )
        if r and not r.encoding:
            r.encoding = "utf-8"

        if (r.status_code != 200) or len(r.content) == 0:
            # logger.info(u"r.status_code: {}".format(r.status_code))
            response_url = get_resolve_url_from_doi_url(doi, connect_timeout, read_timeout)
            return response_url
        else:
            page = r.content
            if related_pub:
                related_pub.tdm_api = page  #archive it for later

    tree = get_tree(page)

    try:
        publication_type = tree.xpath("//doi/@type")[0]
    except IndexError:
        logger.info(u"didn't get a parsable crossref tdm page, so returning resolved url")
        if r:
            return r.url
        else:
            return get_resolve_url_from_doi_url(doi, connect_timeout, read_timeout)

    # logger.info(u"publication_type {}".format(publication_type))
    doi_data_stuff = tree.xpath("//doi_record//journal_article/doi_data/resource/text()".format(publication_type))
    # logger.info(u"doi_data_stuff {}".format(doi_data_stuff))
    # this is ugly, but it works for now.  the last resolved one is the one we want.
    try:
        response_url = doi_data_stuff[-1]
    except IndexError:
        return None

    return response_url



def keep_redirecting(r, my_pub):
    # don't read r.content unless we have to, because it will cause us to download the whole thig instead of just the headers

    # 10.5762/kais.2016.17.5.316
    if ("content-length" in r.headers):
        # manually follow javascript if that's all that's in the payload
        file_size = int(r.headers["content-length"])
        if file_size < 500:
            matches = re.findall(ur"<script>location.href='(.*)'</script>", r.content, re.IGNORECASE)
            if matches:
                redirect_url = matches[0]
                if redirect_url.startswith(u"/"):
                    redirect_url = get_link_target(redirect_url, r.url)
                return redirect_url

    # 10.1097/00003643-201406001-00238
    if my_pub and my_pub.is_same_publisher("Ovid Technologies (Wolters Kluwer Health)"):
        matches = re.findall(ur"OvidAN = '(.*?)';", r.content, re.IGNORECASE)
        if matches:
            an_number = matches[0]
            redirect_url = "http://content.wkhealth.com/linkback/openurl?an={}".format(an_number)
            return redirect_url

    return None

def get_session_id():
    return None

def call_requests_get(url,
                      headers={},
                      read_timeout=60,
                      connect_timeout=60,
                      stream=False,
                      related_pub=None,
                      ask_slowly=False):

    if u"doi.org/" in url:
        url = get_crossref_resolve_url(url, related_pub)
        if not url:
            raise NoDoiException
        logger.info(u"new url is {}".format(url))

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

    if not requests_cache_bucket:
        cache_enabled = False

    if related_pub and related_pub.doi and cache_enabled:
        cached_response = get_page_from_cache(url)
        if cached_response:
            logger.info(u"CACHE HIT on {url}".format(url=url))
            return cached_response

    # reset
    os.environ["HTTP_PROXY"] = ""

    try:
        logger.info(u"LIVE GET on {}".format(url))
    except UnicodeDecodeError:
        logger.info(u"LIVE GET on an url that throws UnicodeDecodeError")

    max_tries = 1
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
            tries += 1
            if tries >= max_tries:
                logger.info(u"in http_get, tried too many times, giving up")
                raise
            else:
                logger.info(u"in http_get, got an exception, trying again")
        finally:
            logger.info(u"finished http_get for {} in {} seconds".format(url, elapsed(start_time, 2)))

    if related_pub and related_pub.doi:
        if r and not is_response_too_large(r) and cache_enabled:
            store_page_in_cache(url, r, related_pub.doi)

    return r


def get_page_from_cache(url):
    cache_key = url
    cache_data = get_cache_entry(cache_key)
    if cache_data:
        url = cache_data["headers"].get("url", None)
        requested_url = cache_data["headers"].get("requested-url", None)
        return CachedResponse(**{"content": cache_data["content"],
                                 "requested-url": requested_url,
                                 "url": url,
                                 "headers": cache_data["headers"]})
    return None


def store_page_in_cache(url, response, doi):
    metadata = {}
    for (k, v) in response.headers.iteritems():
        if k.lower() in ["content-type", "content-disposition"]:
            metadata[k] = v
    metadata["url"] = response.url
    metadata["requested-url"] = url
    if doi:
        metadata["doi"] = doi
    cache_key = url
    set_cache_entry(cache_key, response.content, metadata)




def _build_hash_key(key):
    json_key = json.dumps(key)
    hash_key = hashlib.md5(json_key.encode("utf-8")).hexdigest()
    return hash_key


def get_cache_entry(url):
    """ Get an entry from the cache, returns None if not found """
    hash_key = _build_hash_key(url)
    k = boto.s3.key.Key(requests_cache_bucket)
    k.key = hash_key
    headers = {}

    try:
        file_contents = k.get_contents_as_string()
    except boto.exception.S3ResponseError:
        # logger.info(u"CACHE MISS: couldn't find {}, aka {}".format(hash_key, url))
        # not in cache
        return None

    try:
        remote_key = requests_cache_bucket.get_key(hash_key)
        headers = remote_key.metadata
        headers["content-type"] = k.content_type
        headers["content-disposition"] = k.content_disposition
    except boto.exception.S3ResponseError:
        # no metadata
        # that's ok
        pass

    # logger.info(u"*** {} {} {}".format(url, hash_key, headers))

    return {"content": file_contents, "headers": headers}

def set_cache_entry(url, content, metadata):
    if sys.getsizeof(content) > MAX_PAYLOAD_SIZE_BYTES:
        logger.info(u"Not caching {} because payload is too large: {}".format(
            url, sys.getsizeof(content)))
        return
    hash_key = _build_hash_key(url)
    # logger.info(u"*** {} {}".format(url, hash_key))

    k = boto.s3.key.Key(requests_cache_bucket)
    k.key = hash_key
    k.set_contents_from_string(content)

    if metadata:
        k.set_remote_metadata(metadata, {}, True)

    # remote_key = requests_cache_bucket.get_key(hash_key)
    # logger.info(u"metadata: {}".format(remote_key.metadata))

    return

