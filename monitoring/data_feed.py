import json
import os
import random
from datetime import datetime, timedelta
from time import time

import dateutil.parser
import requests
from slackclient import SlackClient

from app import logger
from changefile import valid_changefile_api_keys, DAILY_FEED, WEEKLY_FEED
from util import elapsed
from monitoring.slack import post_alert

slack_token = os.environ['SLACK_BOT_TOKEN']
sc = SlackClient(slack_token)


def test_changefile_listing_endpoint(feed):
    api_key = random.choice(valid_changefile_api_keys())
    url = u'https://api.unpaywall.org/feed/changefiles?api_key={}&interval={}'.format(api_key, feed['interval'])
    start = time()
    r = requests.get(url)
    et = elapsed(start)

    if et > 25:
        post_alert(u'warning: changefile listing at {} took {} seconds'.format(url, et))

    if r.status_code != 200:
        post_alert(u'warning: HTTP status {} from {}'.format(r.status_code, url))
    try:
        file_listing = r.json()
        logger.info(u'got response from {} in {} seconds: {} files listed'.format(
            url,
            et,
            len(file_listing['list'])
        ))
    except Exception as e:
        post_alert(u'warning: changefile listing at {} not valid JSON ({}): {}'.format(url, e.message, r.content))


def _latest_file(filetype, list_api_response):
    return sorted(
        [f for f in list_api_response['list'] if f['filename'].endswith(filetype + '.gz')],
        key=lambda x: x['last_modified'],
        reverse=True
    )[0]


def _ensure_max_age(feed, filedata, max_age):
    file_date = dateutil.parser.parse(filedata['last_modified'])
    file_age = datetime.utcnow() - file_date
    if file_age > max_age:
        post_alert(u"warning: most recent {}'s {} data feed file was generated {}".format(
            feed['interval'],
            filedata['filetype'],
            file_date
        ))


def _ensure_size_in_range(feed, filedata, min_lines, max_lines):
    num_lines = int(filedata['lines'])
    if not (num_lines >= min_lines and num_lines <= max_lines):
        post_alert(u"warning: most recent {}'s {} data feed file had {} lines, expected between {} and {}".format(
            feed['interval'],
            filedata['filetype'],
            num_lines,
            min_lines,
            max_lines
        ))


def test_latest_changefile_size(feed, min_lines, max_lines):
    api_key = random.choice(valid_changefile_api_keys())
    url = u'https://api.unpaywall.org/feed/changefiles?api_key={}&interval={}'.format(api_key, feed['interval'])
    changefiles = requests.get(url).json()

    latest_jsonl = _latest_file('jsonl', changefiles)
    logger.info(u'latest jsonl file:\n{}'.format(json.dumps(latest_jsonl, indent=4)))
    _ensure_size_in_range(feed, latest_jsonl, min_lines, max_lines)


def test_latest_changefile_age(feed, age):
    api_key = random.choice(valid_changefile_api_keys())
    url = u'https://api.unpaywall.org/feed/changefiles?api_key={}&interval={}'.format(api_key, feed['interval'])
    changefiles = requests.get(url).json()

    latest_jsonl = _latest_file('jsonl', changefiles)
    logger.info(u'latest jsonl file:\n{}'.format(json.dumps(latest_jsonl, indent=4)))
    _ensure_max_age(feed, latest_jsonl, age)


if __name__ == '__main__':
    test_changefile_listing_endpoint(WEEKLY_FEED)
    test_latest_changefile_age(WEEKLY_FEED, timedelta(days=7, hours=12))
    test_latest_changefile_size(WEEKLY_FEED, 1000000, 8000000)

    test_changefile_listing_endpoint(DAILY_FEED)
    test_latest_changefile_age(DAILY_FEED, timedelta(days=1, hours=2))
    test_latest_changefile_size(DAILY_FEED, 30000, 2500000)
