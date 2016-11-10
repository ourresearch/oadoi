import os
import sys
import hashlib
import json
import requests
import socket

from app import requests_cache_bucket


MAX_PAYLOAD_SIZE_BYTES = 1000*1000 # 1mb
CACHE_FOLDER_NAME = "tng-requests-cache"


class CachedResponse:
    def __init__(self, url, file_contents, doi=None):
        self.status_code = cache_data['status_code']
        self.url = url
        self.text = file_contents
        self.headers = {}

    @property
    def content(self):
        return self.text

    # allows it to be treated the same way as a streaming response object
    def close(self):
        pass


def http_get(url, headers={}, timeout=20, stream=False, cache_enabled=False, allow_redirects=True):
    if not cache_client:
        cache_enabled = False

    if cache_enabled:
        cache = Cache()
        cached_response = get_page_from_cache(url, headers, allow_redirects, cache)
        if cached_response:
            print u"CACHE HIT on {url}".format(url=url)
            return cached_response

    try:
        # try:
        #     print u"LIVE GET on {url}".format(url=url)
        # except UnicodeDecodeError:
        #     print u"LIVE GET on an url that throws UnicodeDecodeError"

        r = requests.get(url,
                         headers=headers,
                         timeout=timeout,
                         stream=stream,
                         allow_redirects=allow_redirects,
                         verify=False)

        if r and not r.encoding:
            r.encoding = "utf-8"
        if r and cache_enabled:
            requests_cache_bucket.store_page_in_cache(url, cache)

    except (requests.exceptions.Timeout, socket.timeout) as e:
        print u"timed out on GET on {url}".format(url=url)
        raise

    except requests.exceptions.RequestException as e:
        print u"RequestException on GET on {url}".format(url=url)
        raise

    return r



def store_page_in_cache(url, file_contents, doi):
    cache_key = url

    cache_data = {
        'text':             response.text,
        'status_code':      response.status_code,
        'headers':          json.dumps(headers_string),
        'url':              response.url
    }
    cache.set_cache_entry(cache_key, cache_data)




def _build_hash_key(key):
    json_key = json.dumps(key)
    hash_key = hashlib.md5(json_key.encode("utf-8")).hexdigest()
    return hash_key

def _get_client():
    return cache_client

def get_cache_entry(key):
    """ Get an entry from the cache, returns None if not found """
    mc = _get_client()
    hash_key = _build_hash_key(key)
    full_key_name = os.path.join(CACHE_FOLDER_NAME, hash_key)
    k = cache_client.new_key(full_key_name)
    file_contents = k.get_contents_as_string()
    return CachedResponse(file_contents)

def set_cache_entry(key, file_contents, doi=None):
    if sys.getsizeof(file_contents) > MAX_PAYLOAD_SIZE_BYTES:
        print u"Not caching because payload is too large"
        return None
    mc = _get_client()
    hash_key = _build_hash_key(key)
    full_key_name = os.path.join(CACHE_FOLDER_NAME, hash_key)
    k = cache_client.new_key(full_key_name)
    length = k.set_contents_from_file(file_contents)
    if length and doi:
        k.set_metadata('doi', doi)
    return length

