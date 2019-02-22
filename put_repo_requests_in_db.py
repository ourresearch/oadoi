import csv
import os
import json
import gspread
import datetime
import unicodecsv as csv
from oauth2client.service_account import ServiceAccountCredentials

from app import db
from util import safe_commit
from repository import Endpoint
from repository import Repository
from repository import RepoRequest


def get_repo_request_rows():

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
    return rows

def save_repo_request_rows(rows):

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
            print u"adding repo request {}".format(my_repo_request)
            db.session.merge(my_repo_request)

        safe_commit(db)


def add_endpoint(my_request):
    matching_endpoint = Endpoint()

    if not my_request.pmh_url:
        return None

    matching_endpoint.pmh_url = my_request.pmh_url

    repo_matches = my_request.matching_repositories()
    if repo_matches:
        matching_repo = repo_matches[0]
        print u"yay! for {} {} matches repository {}".format(
            my_request.institution_name, my_request.repo_name, matching_repo)
    else:
        print u"no matching repository for {}: {}".format(
            my_request.institution_name, my_request.repo_name)
        matching_repo = Repository()

    # overwrite stuff with request
    matching_repo.institution_name = my_request.institution_name
    matching_repo.repository_name = my_request.repo_name
    matching_repo.home_page = my_request.repo_home_page
    matching_endpoint.repo_unique_id = matching_repo.id
    matching_endpoint.email = my_request.email
    matching_endpoint.repo_request_id = my_request.id

    # matching_endpoint.ready_to_run = True

    db.session.merge(matching_endpoint)
    db.session.merge(matching_repo)
    print u"added {} {}".format(matching_endpoint, matching_repo)

    safe_commit(db)

    return matching_endpoint




if __name__ == "__main__":
    rows = get_repo_request_rows()
    save_repo_request_rows(rows)

    my_requests = RepoRequest.query.all()
    for my_request in my_requests:
        if not my_request.is_duplicate:
            endpoint_with_this_id = Endpoint.query.filter(Endpoint.repo_request_id==my_request.id).first()
            if not endpoint_with_this_id:

                if my_request.pmh_url is not None:
                    print u"{} adding endpoint for {}".format(my_request.id, my_request)
                    # add_endpoint(my_request)

