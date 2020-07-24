import json

import boto
from sqlalchemy import sql

from app import db

WEEKLY_FEED = {
    'name': 'unpaywall-data-feed',
    'bucket': 'unpaywall-data-feed',
    'endpoint': 'feed',
    'file_dates': lambda filename: {
        'from_date': filename.split("_")[0].split("T")[0],
        'to_date': filename.split("_")[2].split("T")[0]
    },
}

DAILY_FEED = {
    'name': 'unpaywall-daily-data-feed',
    'bucket': 'unpaywall-daily-data-feed',
    'endpoint': 'daily-feed',
    'file_dates': lambda filename: {
        'date': filename.split("T")[0]
    },
}


def valid_changefile_api_keys():
    return [r[0] for r in db.session.execute(
        "select api_key from data_feed_api_keys where not trial or now() between begins and ends + '7 days'::interval"
    ).fetchall()]


def get_file_from_bucket(filename, api_key, feed=WEEKLY_FEED):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(feed['bucket'])
    key = bucket.lookup(filename)
    return key


def get_changefile_dicts(api_key, feed=WEEKLY_FEED):
    response_dict = db.engine.execute(
        sql.text(u'select changefile_dicts from changefile_dicts where feed = :feed').bindparams(feed=feed['name'])
    ).fetchone()[0]

    return json.loads(response_dict.replace('__DATA_FEED_API_KEY__', api_key))
