import os
import sys
import hashlib
import json
import requests
import socket
import boto

from app import requests_cache_bucket


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
        print u"can't tell if page is too large, no Content-Length header {}".format(r.url)
        return False

    content_length = r.headers["Content-Length"]
    # if is bigger than 1 MB, don't keep it don't parse it, act like we couldn't get it
    # if doing 100 in parallel, this would be 100MB, which fits within 512MB dyno limit
    if int(content_length) >= (1 * 1000 * 1000):
        print u"Content Too Large on GET on {url}".format(url=r.url)
        return True
    return False


def http_get(url, headers={}, read_timeout=20, stream=False, cache_enabled=True, allow_redirects=True, doi=None):
    if not requests_cache_bucket:
        cache_enabled = False

    if doi and cache_enabled:
        cached_response = get_page_from_cache(url)
        if cached_response:
            print u"CACHE HIT on {url}".format(url=url)
            return cached_response

    if not doi:
        headers["User-Agent"] = "oaDOI"
        headers["From"] = "team@impactstory.org"

    try:
        try:
            print u"LIVE GET on {url}".format(url=url)
        except UnicodeDecodeError:
            print u"LIVE GET on an url that throws UnicodeDecodeError"

        connect_timeout = 3
        r = requests.get(url,
                         headers=headers,
                         timeout=(connect_timeout, read_timeout),
                         stream=stream,
                         allow_redirects=allow_redirects,
                         verify=False)

        if r and not r.encoding:
            r.encoding = "utf-8"

        if doi:
            if r and not is_response_too_large(r) and cache_enabled:
                store_page_in_cache(url, r, doi)

    except (requests.exceptions.Timeout, socket.timeout) as e:
        print u"timed out on GET on {url}".format(url=url)
        raise

    except requests.exceptions.RequestException as e:
        print u"RequestException on GET on {url}".format(url=url)
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

