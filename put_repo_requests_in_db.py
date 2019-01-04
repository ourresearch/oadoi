import csv
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials




# this file inspired by https://www.twilio.com/blog/2017/02/an-easy-way-to-read-and-write-to-a-google-spreadsheet-in-python.html

# use creds to create a client to interact with the Google Drive API
scopes = ['https://spreadsheets.google.com/feeds']
json_creds = os.getenv("GOOGLE_SHEETS_CREDS_JSON")

creds_dict = json.loads(json_creds)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n")
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
client = gspread.authorize(creds)

# Find a workbook by url
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1RcQuetbKVYRRf0GhGZQi38okY8gT1cPUs6l3RM94yQo/edit#gid=704459328")
sheet = spreadsheet.sheet1

# Extract and print all of the values
rows = sheet.get_all_records()
print(rows)

# import unicodecsv as csv
#
# with open('out.csv','wb') as f:
#     w = csv.DictWriter(f, fieldnames=sorted(rows[0].keys()), encoding='utf-8-sig')
#     w.writeheader()
#     w.writerows(rows)
#
# # then do this https://cloud.google.com/bigquery/docs/loading-data-local
#
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
#         location='US',  # Must match the destination dataset location.
#         job_config=job_config)  # API request
#
# job.result()  # Waits for table load to complete.
#
# print('Loaded {} rows into {}:{}.'.format(
#     job.output_rows, dataset_id, table_id))