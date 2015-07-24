import requests
from requests.auth import HTTPBasicAuth
import os

import logging


logger = logging.getLogger("github")

user = os.environ["GITHUB_CLIENT_ID"]
password = os.environ["GITHUB_CLIENT_SECRET"]
users_url_template = "https://api.github.com/users/%s"
repos_url_template = "https://api.github.com/users/%s/repos"

def get_profile_data(username):
    users_url = users_url_template % username
    profile_data = requests.get(users_url, auth=(user, password))
    return profile_data.json()

def get_repo_data(username):
    repos_url = repos_url_template % username
    print repos_url
    repo_data = requests.get(repos_url, auth=(user, password))
    print repo_data.json()
    return repo_data.json()




