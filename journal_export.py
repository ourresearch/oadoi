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

    journal_stats_rows = db.engine.execute(sql.text(
        'select {stats_fields} from oa_rates_by_journal_year where issn_l is not null and year is not null'.format(stats_fields=', '.join(stats_fields))
    )).fetchall()

    journal_stats = [dict(list(zip(stats_fields, row))) for row in journal_stats_rows]

    csv_filename = tempfile.mkstemp()[1]

    # look up publisher and issns once
    issn_rows = db.engine.execute(sql.text('select issn_l, publisher, issns from journal')).fetchall()
    journals = defaultdict(dict)
    for row in issn_rows:
        journals[row[0]]['publisher'] = row[1]
        journals[row[0]]['issns'] = row[2]

    # look up observed oa years
    observed_oa_rows = db.engine.execute(sql.text('select issn_l, oa_year from journal_oa_start_year_patched')).fetchall()
    observed_oa_years = {}
    for row in observed_oa_rows:
        observed_oa_years[row[0]] = row[1]

    # build doaj issn year dict
    doaj_issn_years = {}
    for row in doaj_issns:
        issn_no_hyphen = row[0]
        issn = issn_no_hyphen[0:4] + '-' + issn_no_hyphen[4:8]
        doaj_issn_years[issn] = row[2]

    # build doaj title year dict
    doaj_title_years = {}
    for row in doaj_titles:
        title = row[0]
        title = title.strip().lower()
        doaj_title_years[title] = row[2]

    def in_doaj_via_issn(issns, year):
        for issn in issns:
            if issn in doaj_issn_years and doaj_issn_years[issn] and year >= doaj_issn_years[issn]:
                return True
        return False

    def in_doaj_via_title(title, year):
        if not title:
            return False

        title = title.encode('utf-8')
        title = oa_local.doaj_journal_name_substitutions().get(title, title)

        if title in oa_local.doaj_titles_to_skip():
            return False

        title = title.strip().lower()

        if title in doaj_title_years and doaj_title_years[title] and year >= doaj_title_years[title]:
            return True

        return False

    # add is_in_doaj, is_gold_journal
    stats_fields.append('is_in_doaj')
    stats_fields.append('is_gold_journal')
    for row in journal_stats:
        issn_l = row['issn_l']
        year = row['year']
        all_issns = set(journals.get(issn_l, {}).get('issns') or [])
        all_issns.add(issn_l)
        all_issns = list(all_issns)
        publisher = journals.get(issn_l, {}).get('publisher', None)

        row['is_in_doaj'] = True if (
            in_doaj_via_issn(all_issns, year) or
            in_doaj_via_title(row['title'], year)
        ) else False

        row['is_gold_journal'] = True if (
            row['is_in_doaj'] or
            oa_local.is_open_via_publisher(publisher) or
            oa_local.is_open_via_manual_journal_setting(all_issns, year) or
            (issn_l in observed_oa_years and year >= observed_oa_years[issn_l])
        ) else False

    with gzip.open(csv_filename, 'wb') as csv:
        writer = unicodecsv.DictWriter(csv, stats_fields, dialect='excel', encoding='utf-8')
        writer.writeheader()

        for row in journal_stats:
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
