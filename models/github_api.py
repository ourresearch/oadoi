import os
import logging
import requests
from urlparse import urlparse
import random
from time import sleep
from time import time
from util import elapsed
import json
import subprocess32
import zipfile
import base64
import re
import ast
from zip_getter import ZipGetter

logger = logging.getLogger("github_api")


class GithubRateLimitException(Exception):
    pass

class NotFoundException(Exception):
    pass

class GithubKeyring():
    def __init__(self):
        self.expired_keys = []

    def get(self):
        """
        get a key. if there is no key, try to see if one is un-expired

        if this raises the GithubRateLimitException,
        you should a lil while before re-calling this, it will hit the
         network a lot if none of the keys are un-expired
        """
        try:
            return self._get_good_key()
        except ValueError:
            print "no good key found so double-checking expired keys"
            self.update_expired_keys()
            # try same thing again, once more...hopefully a key has un-expired.
            try:
                return self._get_good_key()
            except ValueError:  # no more tries for you.
                raise GithubRateLimitException

    def update_expired_keys(self):
        previously_expired_keys = self.expired_keys
        self.expired_keys = []
        for login, token in previously_expired_keys:
            remaining = self._check_remaining_for_key(login, token)
            if remaining == 0:
                self.expired_keys.append([login, token])

    def expire_key(self, login, token):
        print "expiring key:", login
        self.expired_keys.append([login, token])

    def report(self):
        print "remaining calls by key: "
        total_remaining = 0
        for login, token in self._keys_from_env():
            remaining = self._check_remaining_for_key(login, token)
            total_remaining += remaining
            print "{login:>16}: {remaining}".format(
                login=login,
                remaining=remaining
            )

        print "{:>16}: {}".format(
            "TOTAL",
            total_remaining
        )
        print "\n"

    def _get_good_key(self):
        good_keys = [k for k in self._keys_from_env() if k not in self.expired_keys]

        # this throws a value error if no good keys
        ret_key = random.sample(good_keys, 1)[0]
        return ret_key


    def _check_remaining_for_key(self, login, token):
        url = "https://api.github.com/rate_limit"
        r = requests.get(url, auth=(login, token))
        return r.json()["rate"]["remaining"]

    def _keys_from_env(self):
        tokens_str = os.environ["GITHUB_TOKENS"]
        return [t.split(":") for t in tokens_str.split(",")]





# this needs to be a global that the whole application imports and uses
keyring = GithubKeyring()


def github_zip_getter_factory(login, repo_name):
    url = "https://codeload.github.com/{login}/{repo_name}/legacy.zip/master".format(
        login=login,
        repo_name=repo_name
    )
    getter = ZipGetter(url)
    return getter

    #url = "https://api.github.com/repos/{login}/{repo_name}/zipball/master".format(
    #    login=login,
    #    repo_name=repo_name
    #)
    #login, token = keyring.get()
    #getter = ZipGetter(url, login, token)
    #return getter




def make_ratelimited_call(url):

    login, token = keyring.get()

    # assuming rate limited calls will never time out
    requests.packages.urllib3.disable_warnings()            
    r = requests.get(url, auth=(login, token))

    calls_remaining = r.headers["X-RateLimit-Remaining"]

    print "{status_code}: {url}.  {rate_limit} calls remain for {login}".format(
        status_code=r.status_code,
        url=url,
        rate_limit=calls_remaining,
        login=login
    )

    # deal w expired keys
    if int(calls_remaining) == 0:
        # this key is expired.

        keyring.expire_key(login, token)
        if r.status_code < 400:
            pass  # key just expired, but we got good data this call

        elif r.status_code == 403 or r.status_code == 401:
            # key is dead, and also we got no data. try again.
            print "error: got status_code", r.status_code
            return make_ratelimited_call(url)


    # return what we got
    if r.status_code >= 400:
        return {
            "error_code": r.status_code,
            "msg": r.text
        }
    else:
        try:
            return r.json()
        except ValueError:
            return {
                "error_code": r.status_code,
                "msg": "no json in response"
            }




def get_profile(login):
    url = "https://api.github.com/users/{login}".format(
        login=login
    )
    return make_ratelimited_call(url)





def get_requirements_txt_contents(login, repo_name):
    url = 'https://api.github.com/repos/{login}/{repo_name}/contents/requirements.txt'.format(
        login=login,
        repo_name=repo_name
    )
    resp = make_ratelimited_call(url)
    try:
        return base64.decodestring(resp["content"])
    except KeyError:
        raise NotFoundException


def get_setup_py_contents(login, repo_name):
    url = 'https://api.github.com/repos/{login}/{repo_name}/contents/setup.py'.format(
        login=login,
        repo_name=repo_name
    )
    resp = make_ratelimited_call(url)
    try:
        return base64.decodestring(resp["content"])
    except KeyError:
        raise NotFoundException


def get_cran_descr_contents(login, repo_name):
    url = 'https://api.github.com/repos/{login}/{repo_name}/contents/DESCRIPTION'.format(
        login=login,
        repo_name=repo_name
    )
    resp = make_ratelimited_call(url)
    try:
        return base64.decodestring(resp["content"])
    except KeyError:
        raise NotFoundException





def get_repo_contributors(login, repo_name):
    if login is None or repo_name is None:
        return None

    url = "https://api.github.com/repos/{username}/{repo_name}/contributors?per_page=100".format(
        username=login,
        repo_name=repo_name
    )
    contribs = make_ratelimited_call(url)
    if isinstance(contribs, dict):  # it's our error object, not a return.
        return contribs
    else:
        ret = []
        for contrib in contribs:
            ret.append({
                "login": contrib["login"],
                "contributions": contrib["contributions"]
            })
        return ret


def get_repo_data(login, repo_name, trim=True):
    trim_these_keys = [
        "owner",
        "organization",
        "parent",
        "source"
    ]

    url = "https://api.github.com/repos/{login}/{repo_name}".format(
        login=login,
        repo_name=repo_name
    )
    resp_dict = make_ratelimited_call(url)
    if trim:
        ret = {}
        for k, v in resp_dict.iteritems():
            if k in trim_these_keys or k.endswith("url"):
                pass  # this key not returned
            else:
                ret[k] = v
    else:
        ret = resp_dict

    return ret



def login_and_repo_name_from_url(url):
    username = None
    repo_name = None

    print "trying this url", url

    try:
        path = urlparse(url).path
        netloc = urlparse(url).netloc
    except AttributeError:  # there's no url
        return [None, None]

    netloc_parts = netloc.split('.')
    path_parts = filter(None, path.split("/"))

    print "here is the path, netloc", netloc_parts, path_parts

    if netloc_parts[1:] == ['github', 'io'] and len(path_parts) == 1:
        username = netloc_parts[0]
        repo_name = path_parts[0]

    elif netloc == "github.com" and len(path_parts) == 2:
        username = path_parts[0]
        repo_name = path_parts[1]

    return [username, repo_name]





def check_keys():
    keyring.report()




"""useful sql for checking speed of things going into the database"""
# update github_repo set dependency_lines=null where dependency_lines is not null;
# update github_repo set zip_download_elapsed=null where zip_download_elapsed is not null;
# update github_repo set zip_grep_elapsed=null where zip_grep_elapsed is not null;
# update github_repo set zip_download_size=null where zip_download_size is not null;
# update github_repo set zip_download_error=null where zip_download_error is not null;

# select count(*) as count_rows,
#     sum(zip_download_elapsed) as download, 
#     sum(zip_grep_elapsed) as grep, 
#     sum(zip_download_elapsed) + sum(zip_grep_elapsed) as total,
#     (sum(zip_download_elapsed) + sum(zip_grep_elapsed)) / count(*) as seconds_per_row
#     from github_repo
#     where zip_download_elapsed is not null
    
# select login, repo_name, zip_download_elapsed, zip_grep_elapsed, zip_download_elapsed+zip_grep_elapsed as total, zip_download_size
# from github_repo
# where zip_download_elapsed is not null
# order by login, repo_name









