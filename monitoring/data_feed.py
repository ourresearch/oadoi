import json
import os
import random
from datetime import datetime, timedelta
from time import time

import dateutil.parser
import requests
from slackclient import SlackClient

from app import logger
from changefile import valid_changefile_api_keys
from util import elapsed

slack_token = os.environ['SLACK_BOT_TOKEN']
sc = SlackClient(slack_token)


def _post_alert(message):
    sc.api_call(
        "chat.postMessage",
        channel="#general",
        text=message
    )


def test_changefile_listing_endpoint():
    api_key = random.choice(valid_changefile_api_keys())
    url = u'https://api.unpaywall.org/feed/changefiles?api_key={}'.format(api_key)
    start = time()
    r = requests.get(url)
    et = elapsed(start)

    if et > 25:
        _post_alert(u'warning: changefile listing at {} took {} seconds'.format(url, et))

    if r.status_code != 200:
        _post_alert(u'warning: HTTP status {} from {}'.format(r.status_code, url))
    try:
        file_listing = r.json()
        logger.info(u'got response from {} in {} seconds: {} files listed'.format(
            url,
            et,
            len(file_listing['list'])
        ))
    except Exception as e:
        _post_alert(u'warning: changefile listing at {} not valid JSON ({}): {}'.format(url, e.message, r.content))


def _latest_file(filetype, list_api_response):
    return sorted(
        [f for f in list_api_response['list'] if f['filename'].endswith(filetype + '.gz')],
        key=lambda x: x['last_modified'],
        reverse=True
    )[0]


def _ensure_max_age(filedata, max_age):
    file_date = dateutil.parser.parse(filedata['last_modified'])
    file_age = datetime.utcnow() - file_date
    if file_age > max_age:
        _post_alert(u'warning: most recent data feed {} file was generated {}'.format(filedata['filetype'], file_date))


def test_latest_changefile_age():
    api_key = random.choice(valid_changefile_api_keys())
    url = u'https://api.unpaywall.org/feed/changefiles?api_key={}'.format(api_key)
    changefiles = requests.get(url).json()

    latest_csv = _latest_file('csv', changefiles)
    logger.info(u'latest csv file:\n{}'.format(json.dumps(latest_csv, indent=4)))
    _ensure_max_age(latest_csv, timedelta(days=7, hours=12))

    latest_jsonl = _latest_file('jsonl', changefiles)
    logger.info(u'latest jsonl file:\n{}'.format(json.dumps(latest_jsonl, indent=4)))
    _ensure_max_age(latest_jsonl, timedelta(days=7, hours=12))


if __name__ == '__main__':
    test_changefile_listing_endpoint()
    test_latest_changefile_age()