import requests
from requests.auth import HTTPBasicAuth
import os

import logging


logger = logging.getLogger("github")

# generated the "OAuth Personal Access Token" token here:  https://github.com/settings/tokens/new
user = os.environ["GITHUB_OAUTH_USERNAME"]
password = os.environ["GITHUB_OAUTH_ACCESS_TOKEN"]

users_url_template = "https://api.github.com/users/%s"
repos_url_template = "https://api.github.com/users/%s/repos?per_page=100"

def get_profile_data(username):
    users_url = users_url_template % username
    profile_data = requests.get(users_url, auth=(user, password))
    return profile_data.json()

def get_repo_data(username):
    repos_url = repos_url_template % username
    print repos_url
    repo_data = requests.get(repos_url, auth=(user, password))
    return repo_data.json()




