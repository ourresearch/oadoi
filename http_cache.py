import os
import sys
import hashlib
import json
import redis
import requests
import socket

REDIS_CACHE_DATABASE_NUMBER = 0
MAX_PAYLOAD_SIZE_BYTES = 1000*1000 # 1mb
MAX_CACHE_SIZE_BYTES = 300*1000*1000 #300mb
MAX_CACHE_DURATION = 60*60*24*7 # one week

cache_client = redis.from_url(os.getenv("REDIS_URL"), REDIS_CACHE_DATABASE_NUMBER)


def http_get(url, headers={}, timeout=20, stream=False, cache_enabled=True, allow_redirects=True):
    if cache_enabled:
        cache = Cache(MAX_CACHE_DURATION)
        cached_response = get_page_from_cache(url, headers, allow_redirects, cache)
        if cached_response:
            print u"CACHE HIT on {url}".format(url=url)
            return cached_response

    try:
        try:
            print u"LIVE GET on {url}".format(url=url)
        except UnicodeDecodeError:
            print u"LIVE GET on an url that throws UnicodeDecodeError"

        r = requests.get(url,
                         headers=headers,
                         timeout=timeout,
                         stream=stream,
                         allow_redirects=allow_redirects,
                         verify=False)

        if r and not r.encoding:
            r.encoding = "utf-8"
        if r and cache_enabled:
            store_page_in_cache(url, headers, allow_redirects, r, cache)

    except (requests.exceptions.Timeout, socket.timeout) as e:
        print u"timed out on GET on {url}".format(url=url)
        raise

    except requests.exceptions.RequestException as e:
        print u"RequestException on GET on {url}".format(url=url)
        raise

    return r


class CachedResponse:
    def __init__(self, cache_data):
        self.status_code = cache_data['status_code']
        self.url = cache_data['url']
        self.text = cache_data['text'].encode("utf-8")
        self.headers = json.loads(cache_data['headers'])

    @property
    def content(self):
        return self.text

    # allows it to be treated the same way as a streaming response object
    def close(self):
        pass


def get_page_from_cache(url, headers, allow_redirects, cache):
    cache_key = headers.copy()
    cache_key.update({"url":url, "allow_redirects":allow_redirects})
    cache_data = cache.get_cache_entry(cache_key)

    # use it if it was a 200, otherwise go get it again
    if cache_data and (cache_data['status_code'] == 200):
        # print u"returning from cache: %s" %(url)
        return CachedResponse(cache_data)
    return None

def store_page_in_cache(url, headers, allow_redirects, response, cache):
    cache_key = headers.copy()
    cache_key.update({"url":url, "allow_redirects":allow_redirects})
    if response.headers:
        headers_string = dict((str(k), str(v)) for (k, v) in response.headers.items())
    else:
        headers_string = ""

    cache_data = {
        'text':             response.text,
        'status_code':      response.status_code,
        'headers':          json.dumps(headers_string),
        'url':              response.url
    }
    cache.set_cache_entry(cache_key, cache_data)



class Cache(object):
    """ Maintains a cache of URL responses in memcached """

    def _build_hash_key(self, key):
        json_key = json.dumps(key)
        hash_key = hashlib.md5(json_key.encode("utf-8")).hexdigest()
        return hash_key

    def _get_client(self):
        return cache_client

    def __init__(self, max_cache_age=60*60):  #one hour
        self.max_cache_age = max_cache_age
        # self.flush_cache()

    def flush_cache(self):
        #empties the cache
        mc = self._get_client()
        mc.flushdb()

    def get_cache_entry(self, key):
        """ Get an entry from the cache, returns None if not found """
        mc = self._get_client()
        hash_key = self._build_hash_key(key)
        response = mc.get(hash_key)
        if response:
            response = json.loads(response)
        return response

    def set_cache_entry(self, key, data):
        """ Store a cache entry """

        if sys.getsizeof(data["text"]) > MAX_PAYLOAD_SIZE_BYTES:
            print u"Not caching because payload is too large"
            return None

        mc = self._get_client()

        if mc.info()["used_memory"] >= MAX_CACHE_SIZE_BYTES:
            print u"Not caching because redis cache is too full"
            return None

        hash_key = self._build_hash_key(key)
        set_response = mc.set(hash_key, json.dumps(data))
        mc.expire(hash_key, self.max_cache_age)

        if not set_response:
            print u"ERROR: Unable to store into Redis. Make sure redis server is running."
        return set_response

