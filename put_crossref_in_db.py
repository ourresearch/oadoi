import os
import sickle
import boto
import datetime
import requests
from time import sleep
from time import time
from urllib import quote
import zlib
import re
import json
import argparse
from sqlalchemy.dialects.postgresql import JSONB


from app import db
from util import JSONSerializerPython2
from util import elapsed
from util import safe_commit


# data from https://archive.org/details/crossref_doi_metadata
# To update the dump, use the public API with deep paging:
# http://api.crossref.org/works?filter=from-update-date:2016-04-01&rows=1000&cursor=*
# The documentation for this feature is available at:
# https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#deep-paging-with-cursors


# @todo replace this by using the one in publication
class Crossref(db.Model):
    id = db.Column(db.Text, primary_key=True)
    api = db.Column(JSONB)

    def __repr__(self):
        return u"<Crossref ({})>".format(self.id)


def is_good_file(filename):
    return "chunk_" in filename


def get_citeproc_date(year=0, month=1, day=1):
    try:
        return datetime.datetime(year, month, day).isoformat()
    except ValueError:
        return None


def build_crossref_record(data):
    record = {}

    simple_fields = [
        "publisher",
        "subject",
        "link",
        "license",
        "funder",
        "type",
        "update-to",
        "clinical-trial-number",
        "ISSN",  # needs to be uppercase
        "ISBN",  # needs to be uppercase
        "alternative-id"
    ]

    for field in simple_fields:
        if field in data:
            record[field.lower()] = data[field]

    if "title" in data:
        if isinstance(data["title"], basestring):
            record["title"] = data["title"]
        else:
            if data["title"]:
                record["title"] = data["title"][0]  # first one
        if "title" in record and record["title"]:
            record["title"] = re.sub(u"\s+", u" ", record["title"])


    if "container-title" in data:
        record["all_journals"] = data["container-title"]
        if isinstance(data["container-title"], basestring):
            record["journal"] = data["container-title"]
        else:
            if data["container-title"]:
                record["journal"] = data["container-title"][-1] # last one

    if "author" in data:
        # record["authors_json"] = json.dumps(data["author"])
        record["all_authors"] = data["author"]
        if data["author"]:
            first_author = data["author"][0]
            if first_author and u"family" in first_author:
                record["first_author_lastname"] = first_author["family"]
            for author in record["all_authors"]:
                if author and "affiliation" in author and not author.get("affiliation", None):
                    del author["affiliation"]


    if "issued" in data:
        # record["issued_raw"] = data["issued"]
        try:
            if "raw" in data["issued"]:
                record["year"] = int(data["issued"]["raw"])
            elif "date-parts" in data["issued"]:
                record["year"] = int(data["issued"]["date-parts"][0][0])
                date_parts = data["issued"]["date-parts"][0]
                pubdate = get_citeproc_date(*date_parts)
                if pubdate:
                    record["pubdate"] = pubdate
        except (IndexError, TypeError):
            pass

    if "deposited" in data:
        try:
            record["deposited"] = data["deposited"]["date-time"]
        except (IndexError, TypeError):
            pass


    record["added_timestamp"] = datetime.datetime.utcnow().isoformat()
    return record






def api_to_db(query_doi=None, first=None, last=None, today=False, threads=0, chunk_size=None):
    i = 0
    records_to_save = []

    headers={"Accept": "application/json", "User-Agent": "impactstory.org"}

    base_url_with_last = "http://api.crossref.org/works?filter=from-created-date:{first},until-created-date:{last}&rows=1000&cursor={next_cursor}"
    base_url_no_last = "http://api.crossref.org/works?filter=from-created-date:{first}&rows=1000&cursor={next_cursor}"
    base_url_doi = "http://api.crossref.org/works?filter=doi:{doi}"

    # but if want all changes, use "indexed" not "created" as per https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#notes-on-incremental-metadata-updates
    # base_url_with_last = "http://api.crossref.org/works?filter=from-indexed-date:{first},until-indexed-date:{last}&rows=1000&cursor={next_cursor}"
    # base_url_no_last = "http://api.crossref.org/works?filter=from-indexed-date:{first}&rows=1000&cursor={next_cursor}"

    next_cursor = "*"
    has_more_responses = True

    if today:
        last = datetime.date.today().isoformat()
        first = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    if not first:
        first = "2016-04-01"

    while has_more_responses:
        if query_doi:
            url = base_url_doi.format(doi=query_doi)
        else:
            if last:
                url = base_url_with_last.format(first=first, last=last, next_cursor=next_cursor)
            else:
                # query is much faster if don't have a last specified, even if it is far in the future
                url = base_url_no_last.format(first=first, next_cursor=next_cursor)

        print "url", url
        start_time = time()
        resp = requests.get(url, headers=headers)
        print "getting crossref response took {} seconds".format(elapsed(start_time, 2))
        if resp.status_code != 200:
            print u"error in crossref call, status_code = {}".format(resp.status_code)
            return

        resp_data = resp.json()["message"]
        next_cursor = resp_data.get("next-cursor", None)
        if next_cursor:
            next_cursor = quote(next_cursor)

        if not resp_data["items"] or not next_cursor:
            has_more_responses = False

        for data in resp_data["items"]:
            # print ":",
            api_raw = {}
            doi = data["DOI"].lower()

            # using _source key for now because that's how it came out of ES and
            # haven't switched everything over yet
            api_raw["_source"] = build_crossref_record(data)
            api_raw["_source"]["doi"] = doi

            record = Crossref(id=doi, api=api_raw)
            db.session.merge(record)
            print u"got record {}".format(record)
            records_to_save.append(record)

            if len(records_to_save) >= 10:
                safe_commit(db)
                print "last deposted date", records_to_save[-1].api["_source"]["deposited"]
                records_to_save = []

        print "at bottom of loop"

    # make sure to get the last ones
    print "saving last ones"
    safe_commit(db)
    print "done everything"






if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = api_to_db
    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first 2006-01-01)")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last 2006-01-01)")

    parser.add_argument('--query_doi', nargs="?", type=str, help="pull in one doi")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in crossref records from last 2 days")

    # for both
    parser.add_argument('--threads', nargs="?", type=int, help="how many threads if multi")
    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")


    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

