#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import json
import argparse
from google.cloud import bigquery
from oauth2client.service_account import ServiceAccountCredentials

from app import db
from util import run_sql

def run_bigquery_query(query):
    setup_bigquery_creds()
    client = bigquery.Client()

    query_job = client.query(query, location="US")
    results = [x for x in query_job.result()]
    return results

def setup_bigquery_creds():
    # get creds and save in a temp file because google needs it like this
    json_creds = os.getenv("GOOGLE_SHEETS_CREDS_JSON")
    creds_dict = json.loads(json_creds)
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_application_credentials.json"
    with open('google_application_credentials.json', 'w') as outfile:
        json.dump(creds_dict, outfile)

def import_from_local_file(temp_data_filename, bq_tablename, columns_to_export, append=True):

    # import the data into bigquery
    (dataset_id, table_id) = bq_tablename.split(".")

    setup_bigquery_creds()
    client = bigquery.Client()
    dataset_ref = client.dataset(dataset_id)
    table_ref = dataset_ref.table(table_id)
    job_config = bigquery.LoadJobConfig()
    job_config.source_format = bigquery.SourceFormat.CSV
    job_config.skip_leading_rows = 1
    job_config.allow_quoted_newlines = True
    job_config.max_bad_records = 1000

    if append:
        job_config.autodetect = False
        job_config.write_disposition = 'WRITE_APPEND'
    else:
        job_config.autodetect = True
        job_config.write_disposition = 'WRITE_TRUNCATE'

    if "*" in columns_to_export or "," in columns_to_export:
        job_config.field_delimiter = ","
    else:
        job_config.field_delimiter = "þ"  # placeholder when only one column and don't want to split it

    with open(temp_data_filename, 'rb') as source_file:
        job = client.load_table_from_file(
            source_file,
            bq_tablename,
            location='US',
            job_config=job_config)  # API request

    job.result()  # Waits for table load to complete.
    print('Loaded {} rows into {}:{}.'.format(job.output_rows, dataset_id, table_id))



def import_data_since_updated_raw(db_tablename, bq_tablename, bq_tablename_for_update_date=None, columns_to_export="*", field_delimeter=","):
    if not bq_tablename_for_update_date:
        bq_tablename_for_update_date = bq_tablename

    # get the max updated date of the stuff already in bigquery
    max_updated = None
    query = u"SELECT cast(max(updated) as string) as result from {}".format(bq_tablename_for_update_date)
    results = run_bigquery_query(query)
    if results:
        max_updated = results[0].result
        print u"max_updated: {}".format(max_updated)
    if not max_updated:
        return

    # export everything from db that is more recent than what is in bigquery into a temporary csv file
    q = """COPY (select {} from {} where updated > ('{}'::timestamp) ) to STDOUT WITH (FORMAT CSV, HEADER)""".format(
            columns_to_export, db_tablename, max_updated)
    print u"\n\n{}\n\n".format(q)

    temp_data_filename = 'data_export.csv'
    cursor = db.session.connection().connection.cursor()
    with open(temp_data_filename, "w") as f:
        cursor.copy_expert(q, f)

    # with open(temp_data_filename,'r') as f:
    #     print f.read()

    import_from_local_file(temp_data_filename, bq_tablename, columns_to_export)


def import_overwrite_data(db_tablename, bq_tablename):
    # export everything from db that is more recent than what is in bigquery into a temporary csv file
    q = """COPY {} to STDOUT WITH (FORMAT CSV, HEADER)""".format(
            db_tablename)
    print u"\n\n{}\n\n".format(q)

    temp_data_filename = 'data_export.csv'
    cursor = db.session.connection().connection.cursor()
    with open(temp_data_filename, "w") as f:
        cursor.copy_expert(q, f)

    # with open(temp_data_filename,'r') as f:
    #     print f.read()

    import_from_local_file(temp_data_filename, bq_tablename, append=False, columns_to_export="*")


def import_updated_data(db_tablename, bq_tablename):
    import_data_since_updated_raw(db_tablename, bq_tablename)

    # approach thanks to https://stackoverflow.com/a/48132644/596939
    query = """DELETE FROM `{}`
                WHERE STRUCT(id, updated) NOT IN (
                        SELECT AS STRUCT id, MAX(updated)
                        FROM `{}`
                        GROUP BY id
                        )""".format(bq_tablename, bq_tablename)
    results = run_bigquery_query(query)
    print u"deleted: {}".format(results)

    query = u"SELECT max(updated) from {}".format(bq_tablename)
    results = run_bigquery_query(query)
    print u"max_updated: {}".format(results)


def import_unpaywall():
    # do a quick check before we start
    query = u"SELECT count(id) from unpaywall.unpaywall"
    results = run_bigquery_query(query)
    print u"count in unpaywall: {}".format(results)

    # first import into unpaywall_raw, then select most recently updated and dedup, then create unpaywall from
    # view that extracts fields from json

    import_data_since_updated_raw("pub",
                    "unpaywall.unpaywall_raw",
                    bq_tablename_for_update_date="unpaywall.unpaywall",
                    columns_to_export="response_jsonb")


    query = """CREATE OR REPLACE TABLE `unpaywall-bhd.unpaywall.unpaywall_raw` AS
                SELECT * EXCEPT(rn)
                FROM (
                  SELECT *, ROW_NUMBER() OVER(PARTITION BY json_extract_scalar(data, '$.doi') order by cast(replace(json_extract(data, '$.updated'), '"', '') as datetime) desc, data) rn
                  FROM `unpaywall-bhd.unpaywall.unpaywall_raw`
                ) 
                WHERE rn = 1"""
    results = run_bigquery_query(query)
    print u"done deduplication"

    # this view uses unpaywall_raw
    query = """create or replace table `unpaywall-bhd.unpaywall.unpaywall` as (select * from `unpaywall-bhd.unpaywall.unpaywall_view`)"""
    results = run_bigquery_query(query)
    print u"done update table from view"

    query = u"SELECT count(id) from unpaywall.unpaywall"
    results = run_bigquery_query(query)
    print u"count in unpaywall: {}".format(results)

    query = u"SELECT max(updated) from unpaywall.unpaywall"
    results = run_bigquery_query(query)
    print u"max_updated in punpaywall: {}".format(results)

# python bigquery_import.py --db pmh_record --bq pmh.pmh_record

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--table', nargs="?", type=str, help="table name in postgres (eg pmh_record)")
    parser.add_argument('--bq', nargs="?", type=str, help="table name in bigquery, including dataset (eg pmh.pmh_record)")

    parsed_args = parser.parse_args()
    if parsed_args.table == "pmh_record":
        import_updated_data("pmh_record", "pmh.pmh_record")
    elif parsed_args.table == "page_new":
        import_updated_data("page_new", "pmh.page_new")
    elif parsed_args.table == "endpoint":
        import_overwrite_data("endpoint", "pmh.endpoint")
    elif parsed_args.table == "repository":
        import_overwrite_data("repository", "pmh.repository")
    elif parsed_args.table == "repo_request":
        import_overwrite_data("repo_request", "pmh.repo_request")
    elif parsed_args.table == "unpaywall":
        import_unpaywall()

# gcloud init --console-only
# gsutil cp unpaywall_snapshot_2018-09-27T192440.jsonl gs://unpaywall-grid/unpaywall
# bq show --schema --format=prettyjson pmh.page_new > schema.json; bq --location=US load --noreplace --source_format=CSV --skip_leading_rows=1 --max_bad_records=1000 --allow_quoted_newlines pmh.page_new gs://unpaywall-grid/pmh/page_new_recent_20190112.csv ./schema.json
# bq show --schema --format=prettyjson pmh.pmh_record > schema.json; bq --location=US load --noreplace --source_format=CSV --skip_leading_rows=1 --max_bad_records=1000 --allow_quoted_newlines pmh.pmh_record gs://unpaywall-grid/pmh/pmh_record_recent_new.csv ./schema.json
# bq show --schema --format=prettyjson unpaywall.unpaywall > schema.json; bq --location=US load --noreplace --source_format=CSV --skip_leading_rows=1 --max_bad_records=1000 --allow_quoted_newlines --field_delimiter=þ unpaywall.unpaywall_raw gs://unpaywall-grid/unpaywall/changed*.jsonl ./schema.json
