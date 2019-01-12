import csv
import os
import json
import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials

from app import db
from util import safe_commit
from repository import Endpoint
from repository import Repository
from repository import RepoRequest


# this file inspired by https://www.twilio.com/blog/2017/02/an-easy-way-to-read-and-write-to-a-google-spreadsheet-in-python.html

# use creds to create a client to interact with the Google Drive API
scopes = ['https://spreadsheets.google.com/feeds']
json_creds = os.getenv("GOOGLE_SHEETS_CREDS_JSON")

creds_dict = json.loads(json_creds)

# hack to get around ugly new line escaping issues
# this works for me, but later found links to what might be cleaner solutions:
# use ast.literal_eval?  https://github.com/googleapis/google-api-go-client/issues/185#issuecomment-422732250
# or maybe dumping like this might fix it? https://coreyward.svbtle.com/how-to-send-a-multiline-file-to-heroku-config

creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n")

# now continue
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
client = gspread.authorize(creds)

# Find a workbook by url
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1RcQuetbKVYRRf0GhGZQi38okY8gT1cPUs6l3RM94yQo/edit#gid=704459328")
sheet = spreadsheet.sheet1

# Extract and print all of the values
rows = sheet.get_all_values()
print(rows[0:1])

import unicodecsv as csv

with open('out.csv','wb') as f:

    w = csv.DictWriter(f, fieldnames=RepoRequest.list_fieldnames(), encoding='utf-8-sig')

    for row in rows[1:]:  # skip header row
        my_repo_request = RepoRequest()
        my_repo_request.set_id_seed(row[0])
        column_num = 0
        for fieldname in RepoRequest.list_fieldnames():
            if fieldname != "id":
                setattr(my_repo_request, fieldname, row[column_num])
                column_num += 1

        w.writerow(my_repo_request.to_dict())
        db.session.merge(my_repo_request)

    safe_commit(db)


my_requests = RepoRequest.query.all()
for my_request in my_requests:
    matching_repo = None
    matching_endpoint = None

    endpoint_matches = my_request.matching_endpoints()
    print u"\n"
    if endpoint_matches:
        matching_endpoint = endpoint_matches[0]
        matching_repo = matching_endpoint.meta
    else:
        print u"no matching endpoint for {}".format(my_request.pmh_url)
        matching_endpoint = Endpoint()
        matching_endpoint.pmh_url = my_request.pmh_url
        # db.session.add(matching_endpoint)

    if matching_repo:
        print u"yay! for {} matches {}".format(my_request.pmh_url, matching_endpoint.pmh_url)
        print u"has repository '{}'".format(matching_repo)
    else:
        repo_matches = my_request.matching_repositories()
        if repo_matches:
            matching_repo = repo_matches[0]
            print u"yay! for {} {} matches repository {}".format(
                my_request.institution_name, my_request.repo_name, matching_repo)
        else:
            print u"no matching repository for {}: {}".format(
                my_request.institution_name, my_request.repo_name)
            matching_repo = Repository()
            # db.session.add(matching_repo)

    # overwrite stuff with request
    matching_repo.institution_name = my_request.institution_name
    matching_repo.repository_name = my_request.repo_name
    matching_repo.home_page = my_request.repo_home_page
    matching_endpoint.repo_unique_id = matching_repo.id
    matching_endpoint.email = my_request.email
    matching_endpoint.repo_request_id = my_request.id

    db.session.merge(matching_endpoint)
    db.session.merge(matching_repo)

    safe_commit(db)


#
# # now save the creds in a temp file because google needs it like this
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_application_credentials.json"
# with open('google_application_credentials.json', 'w') as outfile:
#     json.dump(creds_dict, outfile)
#
# #
# # # then do this https://cloud.google.com/bigquery/docs/loading-data-local
# #
# from google.cloud import bigquery
# client = bigquery.Client()
# filename = 'out.csv'
# dataset_id = 'pmh'
# table_id = 'temp_rr'
#
# dataset_ref = client.dataset(dataset_id)
# table_ref = dataset_ref.table(table_id)
# job_config = bigquery.LoadJobConfig()
# job_config.source_format = bigquery.SourceFormat.CSV
# job_config.skip_leading_rows = 1
# job_config.autodetect = True
#
# with open(filename, 'rb') as source_file:
#     job = client.load_table_from_file(
#         source_file,
#         table_ref,
#         location='US',
#         job_config=job_config)  # API request
#
# job.result()  # Waits for table load to complete.
#
# print('Loaded {} rows into {}:{}.'.format(job.output_rows, dataset_id, table_id))
#
# query = "SELECT * from pmh.temp_rr"
#
# query_job = client.query(query, location="US") # starts the query
#
# for row in query_job:  # fetches results
#     print(row["Email_Address"])
#
