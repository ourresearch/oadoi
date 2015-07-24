import requests
import os

import logging


logger = logging.getLogger("github")

repos_url_template = "https://api.github.com/users/%s/repos?client_id=" + os.environ["GITHUB_CLIENT_ID"] + "&client_secret=" + os.environ["GITHUB_CLIENT_SECRET"]

def get_repo_names(username):
    repos_url = repos_url_template % username
    response = requests.get(repos_url)
    repo_names = [repo["name"] for repo in response.json()]
    return repo_names




