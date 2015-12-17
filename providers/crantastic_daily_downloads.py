import requests
from requests.auth import HTTPBasicAuth
import os

import logging
logger = logging.getLogger("crantastic_daily_downloads")

user = os.environ["GITHUB_OAUTH_USERNAME"]
password = os.environ["GITHUB_OAUTH_ACCESS_TOKEN"]

url_template = "http://cranlogs.r-pkg.org/downloads/daily/1900-01-01:2020-01-01/%s"


def get_data(reponame):
    data_url = url_template % reponame
    print data_url
    response = requests.get(data_url, auth=(user, password))
    if "day" in response.text:
        data = {}
        all_days = response.json()[0]["downloads"]
        data["total_downloads"] = sum([int(day["downloads"]) for day in all_days])
        data["first_download"] = min([day["day"] for day in all_days])
        data["daily_downloads"] = all_days
    else:
        data = None
    return data
