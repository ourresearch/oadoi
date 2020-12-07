import json

import boto
from sqlalchemy import sql

from app import db
from changefile import DAILY_FEED, WEEKLY_FEED
from app import logger


def cache_changefile_dicts(feed):
    logger.info(u'calculating response for {}'.format(feed['name']))

    s3 = boto.connect_s3()
    bucket = s3.get_bucket(feed['bucket'])
    bucket_contents_all = bucket.list()
    bucket_contents = []
    for bucket_file in bucket_contents_all:
        filename = bucket_file.key
        if "changed_dois_with_versions" in filename and any([filename.endswith(x) for x in ['.csv.gz', 'jsonl.gz']]):
            my_key = bucket.get_key(bucket_file.name)
            if my_key.metadata.get("updated", None) is not None:
                bucket_contents.append(my_key)

    response = []
    for bucket_file in bucket_contents:
        simple_key = bucket_file.key
        simple_key = simple_key.replace("changed_dois_with_versions_", "")
        simple_key = simple_key.split(".")[0]
        my_dict = {
            "filename": bucket_file.key,
            "size": bucket_file.size,
            "filetype": bucket_file.name.split(".")[1],
            "url": "http://api.unpaywall.org/{}/{}?api_key=__DATA_FEED_API_KEY__".format(
                feed['changefile-endpoint'], bucket_file.name
            ),
            "last_modified": bucket_file.metadata.get("updated", None),
            "lines": int(bucket_file.metadata.get("lines", 0)),
        }
        my_dict.update(feed['file_dates'](simple_key))
        response.append(my_dict)
    response.sort(key=lambda x:x['filename'], reverse=True)

    query = sql.text(u'''
        insert into changefile_dicts (feed, changefile_dicts) values (:feed, :dicts)
        on conflict (feed) do update set changefile_dicts = excluded.changefile_dicts
    ''')
    db.engine.execute(query.bindparams(feed=feed['name'], dicts=json.dumps(response)))


if __name__ == "__main__":
    cache_changefile_dicts(DAILY_FEED)
    cache_changefile_dicts(WEEKLY_FEED)
