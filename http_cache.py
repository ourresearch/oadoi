import os
import sys
import hashlib
import json
import requests
import socket
import boto
from requests.auth import HTTPProxyAuth

from app import requests_cache_bucket
from app import user_agent_source
from util import clean_doi
from util import get_tree
from util import get_link_target

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
        # print u"can't tell if page is too large, no Content-Length header {}".format(r.url)
        return False

    content_length = r.headers["Content-Length"]
    # if is bigger than 1 MB, don't keep it don't parse it, act like we couldn't get it
    # if doing 100 in parallel, this would be 100MB, which fits within 512MB dyno limit
    if int(content_length) >= (1 * 1000 * 1000):
        print u"Content Too Large on GET on {url}".format(url=r.url)
        return True
    return False

# 10.2514/6.2006-5946!  https://arc.aiaa.org/doi/pdf/10.2514/6.2006-5946
# 10.3410/f.6269956.7654055 none
# 10.2514/6.2006-2106 none  (lots of redirects)
# 10.5040/9780567662088.part-003 none (book)
# 10.1016/j.jvcir.2016.03.027 (elsevier, relative links)
# 10.1002/(sici)1096-911x(200006)34:6<432::aid-mpo10>3.0.co;2-1 (has a blank tdm_api)

# python update.py Crossref.run_with_realtime_scraping --id=10.2514/6.2006-5946

def get_crossref_resolve_url(url, related_pub=None):
    doi = clean_doi(url)

    # cache_enabled = False
    #
    # if not requests_cache_bucket:
    #     cache_enabled = False
    #
    # if cache_enabled:
    #     # use doi to store and retrieve the crossref unixsd+xml api results
    #     cached_response = get_page_from_cache(doi)
    #     if cached_response:
    #         print u"CACHE HIT on {}".format(doi)
    #         return cached_response

    # reset this in case it had been set
    os.environ["HTTP_PROXY"] = ""

    headers = {"Accept": "application/vnd.crossref.unixsd+xml"}
    headers["User-Agent"] = "oaDOI.org"
    headers["From"] = "team@impactstory.org"

    connect_timeout = 30
    read_timeout = 30
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
        print u"r.status_code: {}".format(r.status_code)
        print u"WARNING: no crossref tdm_api for {}, so using resolve url".format(url)
        r = requests.get("http://doi.org/{}".format(doi),
                        allow_redirects=False,
                        timeout=(connect_timeout, read_timeout))
        print u"new responses"
        print u"r.status_code: {}".format(r.status_code)
        print u"r.headers: {}".format(r.headers)
        response_url = r.headers["Location"]
    else:
        page = r.content
        if related_pub:
            related_pub.tdm_api = page  #archive it for later
        tree = get_tree(page)
        publication_type = tree.xpath("//doi/@type")[0]
        print "publication_type", publication_type
        doi_data_stuff = tree.xpath("//doi_record//doi_data/resource/text()".format(publication_type))
        print "doi_data_stuff", doi_data_stuff
        # this is ugly, but it works for now.  the last resolved one is the one we want.
        response_url = doi_data_stuff[-1]

        # if r and cache_enabled:
        #     store_page_in_cache(doi, r, doi)

    print "response_url", response_url
    return response_url


def http_get_with_proxy(url,
             headers={},
             read_timeout=20,
             connect_timeout=10,
             stream=False,
             related_pub=None):

    saved_http_proxy = os.getenv("HTTP_PROXY", "")

    if u"doi.org/" in url:
        url = get_crossref_resolve_url(url, related_pub)
        print u"new url is {}".format(url)

    # proxy things
    os.environ["HTTP_PROXY"] = 'http://{}:DUMMY@proxy.crawlera.com:8010'.format(os.getenv("CRAWLERA_KEY"))
    headers["X-Crawlera-UA"] = "pass"
    headers["X-Crawlera-Session"] = "create"

    # get a non-mobile user agent
    headers["User-Agent"] = user_agent_source.random
    while "mobile" in headers["User-Agent"].lower():
        headers["User-Agent"] = user_agent_source.random

    following_redirects = True
    num_redirects = 0
    cookies = {}
    crawlera_session = None

    read_timeout = 30
    connect_timeout = 30

    while following_redirects:
        print "about to request {}".format(url)
        cookies[url] = "true"
        proxy_url = 'http://{}:DUMMY@proxy.crawlera.com:8010'.format(os.getenv("CRAWLERA_KEY"))
        proxies = {"http": proxy_url}

        r = requests.get(url,
                         headers=headers,
                         timeout=(connect_timeout, read_timeout),
                         stream=stream,
                         proxies=proxies,
                         allow_redirects=False,
                         cookies=cookies,
                         verify=False)

        if r and not r.encoding:
            r.encoding = "utf-8"

        if "X-Crawlera-Error" in r.headers:
            print u"WARNING: X-Crawlera-Error on {}, {}".format(url, r.headers["X-Crawlera-Error"])
        if "X-Crawlera-Next-Request-In" in r.headers:
            print u"WARNING: X-Crawlera rate limit on {}, {}".format(url, r.headers["X-Crawlera-Next-Request-In"])

        num_redirects += 1
        print "status_code:", r.status_code
        if (r.status_code != 301 and r.status_code != 302) or (num_redirects > 5):
            following_redirects = False

        else:
            headers["referer"] = url
            cookies = r.cookies
            # print "cookies", cookies
            # print "response headers", r.headers
            if "X-Crawlera-Session" in r.headers:
                crawlera_session = r.headers["X-Crawlera-Session"]
                print u"new session: {}".format(crawlera_session)
            headers["X-Crawlera-Session"] = crawlera_session
            url = r.headers["Location"]
            if url.startswith("/"):
                url = get_link_target(url, headers["referer"], strip_jsessionid=False)

    # use the proxy to build the url we need to delete the session
    if crawlera_session:
        delete_url = "{}/sessions/{}".format(os.environ["HTTP_PROXY"], crawlera_session)
        requests.delete(delete_url)

    # now set it back to normal
    os.environ["HTTP_PROXY"] = saved_http_proxy

    return r


def http_get(url,
             headers={},
             read_timeout=20,
             connect_timeout=10,
             stream=False,
             cache_enabled=True,
             allow_redirects=True,
             related_pub=None,
             use_proxy=True):

    cache_enabled = False

    if not requests_cache_bucket:
        cache_enabled = False

    if related_pub and related_pub.doi and cache_enabled:
        cached_response = get_page_from_cache(url)
        if cached_response:
            print u"CACHE HIT on {url}".format(url=url)
            return cached_response

    # reset
    os.environ["HTTP_PROXY"] = ""

    try:
        try:
            print u"LIVE GET on {url}".format(url=url)
        except UnicodeDecodeError:
            print u"LIVE GET on an url that throws UnicodeDecodeError"

        if use_proxy:
            r = http_get_with_proxy(url,
                                    headers=headers,
                                    read_timeout=read_timeout,
                                    connect_timeout=connect_timeout,
                                    stream=stream,
                                    related_pub=related_pub)
        else:
            headers["User-Agent"] = "oaDOI.org"
            headers["From"] = "team@impactstory.org"
            r = requests.get(url,
                             headers=headers,
                             timeout=(connect_timeout, read_timeout),
                             stream=stream,
                             allow_redirects=True,
                             verify=False)
        # print r.text[0:1000]
        print "status_code:", r.status_code

        if r and not r.encoding:
            r.encoding = "utf-8"

        if related_pub and related_pub.doi:
            if r and not is_response_too_large(r) and cache_enabled:
                store_page_in_cache(url, r, related_pub.doi)

    except (requests.exceptions.Timeout, socket.timeout) as e:
        print u"timed out on GET on {}: {}".format(url, e)
        raise

    except requests.exceptions.RequestException as e:
        print u"RequestException on GET on {}: {}".format(url, e)
        raise

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
        # print u"CACHE MISS: couldn't find {}, aka {}".format(hash_key, url)
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

    # print "***", url, hash_key, headers

    return {"content": file_contents, "headers": headers}

def set_cache_entry(url, content, metadata):
    if sys.getsizeof(content) > MAX_PAYLOAD_SIZE_BYTES:
        print u"Not caching {} because payload is too large: {}".format(
            url, sys.getsizeof(content))
        return
    hash_key = _build_hash_key(url)
    # print "***", url, hash_key

    k = boto.s3.key.Key(requests_cache_bucket)
    k.key = hash_key
    k.set_contents_from_string(content)

    if metadata:
        k.set_remote_metadata(metadata, {}, True)

    # remote_key = requests_cache_bucket.get_key(hash_key)
    # print "metadata:", remote_key.metadata

    return

