import json

import boto
from sqlalchemy import sql

from app import db
from changefile import DAILY_FEED, WEEKLY_FEED
from app import logger
import unicodecsv
import tempfile
import gzip

def write_journal_csv():
    journals = db.engine.execute(sql.text(u'select issn_l, issns::text, title, publisher from journal')).fetchall()

    csv_filename = tempfile.mkstemp()[1]

    with gzip.open(csv_filename, 'wb') as csv:
        writer = unicodecsv.writer(csv, dialect='excel', encoding='utf-8')
        writer.writerow(('issn_l', 'issns', 'title', 'publisher'))

        for journal in journals:
            writer.writerow(journal)

    return csv_filename


def write_oa_stats_csv():
    stats_fields = (
        'issn_l', 'title', 'year',
        'num_dois', 'num_open', 'open_rate',
        'num_green', 'green_rate',
        'num_bronze', 'bronze_rate',
        'num_hybrid', ' hybrid_rate',
        'num_gold', 'gold_rate'
    )

    journal_stats_rows = db.engine.execute(sql.text(
        u'select {stats_fields} from oa_rates_by_journal_year'.format(stats_fields=', '.join(stats_fields))
    )).fetchall()

    csv_filename = tempfile.mkstemp()[1]

    with gzip.open(csv_filename, 'wb') as csv:
        writer = unicodecsv.writer(csv, dialect='excel', encoding='utf-8')
        writer.writerow(stats_fields)

        for row in journal_stats_rows:
            writer.writerow(row)

    return csv_filename


def upload_journal_file(filename, object_name):
    s3 = boto.connect_s3(host='s3-us-west-2.amazonaws.com')
    bucket = s3.get_bucket('unpaywall-journal-csv')
    boto.s3.key.Key(bucket=bucket, name=object_name).set_contents_from_filename(filename, replace=True)


def get_journal_file_key(filename):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket('unpaywall-journal-csv')
    return bucket.lookup(filename)


if __name__ == "__main__":
    upload_journal_file(write_journal_csv(), u'journals.csv.gz')
    upload_journal_file(write_oa_stats_csv(), u'journal_open_access.csv.gz')
