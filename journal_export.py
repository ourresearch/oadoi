import gzip
import tempfile
from collections import defaultdict

import boto
import unicodecsv
from sqlalchemy import sql

import oa_local
from app import db, doaj_issns, doaj_titles

OA_STATS_FILE = 'journal_open_access.csv.gz'
REPO_FILE = 'repositories.csv.gz'
REQUESTS_FILE = 'extension_requests.csv.gz'
ISSNS_FILE = 'crossref_issns.csv.gz'


def _write_oa_stats_csv():
    # get oa stats by color
    stats_fields = [
        'issn_l', 'title', 'year',
        'num_dois', 'num_open', 'open_rate',
        'num_green', 'green_rate',
        'num_bronze', 'bronze_rate',
        'num_hybrid', 'hybrid_rate',
        'num_gold', 'gold_rate',
    ]

    csv_fields = stats_fields + ['is_in_doaj', 'is_gold_journal']

    journal_stats_rows = db.engine.execute(
        sql.text('''
            select {stats_fields}, doaj.issn_l is not null as is_in_doaj, oa.issn_l is not null as is_gold_journal 
            from oa_rates_by_journal_year
            left join oa_issn_l_years oa using (issn_l, year)
            left join doaj_issn_l_years doaj using (issn_l, year)
            where issn_l is not null and year is not null
        '''.format(stats_fields=', '.join(stats_fields)))
    ).fetchall()

    journal_dicts = [dict(list(zip(csv_fields, row))) for row in journal_stats_rows]

    csv_filename = tempfile.mkstemp()[1]

    with gzip.open(csv_filename, 'wb') as csv:
        writer = unicodecsv.DictWriter(csv, csv_fields, dialect='excel', encoding='utf-8')
        writer.writeheader()

        for row in journal_dicts:
            writer.writerow(row)

    return csv_filename


def _write_repo_csv():
    rows = db.engine.execute(sql.text('''
        select issn_l, endpoint_id, r.repository_name, r.institution_name, r.home_page, e.pmh_url, num_articles
        from num_articles_by_journal_repo
        join endpoint e on e.id = endpoint_id
        join repository r on e.repo_unique_id = r.id
    ''')).fetchall()

    csv_filename = tempfile.mkstemp()[1]

    with gzip.open(csv_filename, 'wb') as csv:
        writer = unicodecsv.writer(csv, dialect='excel', encoding='utf-8')
        writer.writerow(('issn_l', 'endpoint_id', 'repository_name', 'institution_name', 'home_page', 'pmh_url', 'num_articles'))

        for row in rows:
            writer.writerow(row)

    return csv_filename


def _write_crossref_issn_csv():
    issns = db.engine.execute(sql.text('select issn from crossref_issn')).fetchall()
    csv_filename = tempfile.mkstemp()[1]

    with gzip.open(csv_filename, 'wb') as csv:
        writer = unicodecsv.writer(csv, dialect='excel', encoding='utf-8')
        writer.writerow(['issn'])

        for issn in issns:
            writer.writerow(issn)

    return csv_filename


def _write_requests_csv():
    rows = db.engine.execute(sql.text('select month, issn_l, requests from extension_journal_requests_by_month')).fetchall()

    csv_filename = tempfile.mkstemp()[1]

    with gzip.open(csv_filename, 'wb') as csv:
        writer = unicodecsv.writer(csv, dialect='excel', encoding='utf-8')
        writer.writerow(('month', 'issn_l', 'requests'))

        for row in rows:
            writer.writerow(row)

    return csv_filename


def _upload_journal_file(filename, object_name):
    s3 = boto.connect_s3(host='s3-us-west-2.amazonaws.com')
    bucket = s3.get_bucket('unpaywall-journal-csv')
    boto.s3.key.Key(bucket=bucket, name=object_name).set_contents_from_filename(filename, replace=True)


def get_journal_file_key(filename):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket('unpaywall-journal-csv')
    return bucket.lookup(filename)


if __name__ == "__main__":
    _upload_journal_file(_write_oa_stats_csv(), OA_STATS_FILE)
    _upload_journal_file(_write_repo_csv(), REPO_FILE)
    _upload_journal_file(_write_requests_csv(), REQUESTS_FILE)
    _upload_journal_file(_write_crossref_issn_csv(), ISSNS_FILE)
