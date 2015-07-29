import requests
from requests.auth import HTTPBasicAuth
import os

import logging
logger = logging.getLogger("github_subscribers")

user = os.environ["GITHUB_OAUTH_USERNAME"]
password = os.environ["GITHUB_OAUTH_ACCESS_TOKEN"]

url_template = "https://api.github.com/repos/%s/%s/subscribers?per_page=100"


def get_data(username, reponame):
    data_url = url_template % (username, reponame)
    print data_url
    response = requests.get(data_url, auth=(user, password))
    if not "Not Found" in response.text:

        keys_to_return = [
            "avatar_url",
            "html_url",
            "login"
            ]
        all_subscribers_full_response = response.json()
        data = []
        for subscriber in all_subscribers_full_response:
            small_dict = dict([(k, subscriber[k]) for k in keys_to_return if k in subscriber])
            data.append(small_dict)

    else:
        data = None

    return data


