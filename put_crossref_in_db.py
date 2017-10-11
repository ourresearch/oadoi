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
from app import logger
from util import JSONSerializerPython2
from util import elapsed
from util import safe_commit
from publication import Crossref
from publication import build_crossref_record

# data from https://archive.org/details/crossref_doi_metadata
# To update the dump, use the public API with deep paging:
# http://api.crossref.org/works?filter=from-update-date:2016-04-01&rows=1000&cursor=*
# The documentation for this feature is available at:
# https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#deep-paging-with-cursors


def is_good_file(filename):
    return "chunk_" in filename


def get_citeproc_date(year=0, month=1, day=1):
    try:
        return datetime.datetime(year, month, day).isoformat()
    except ValueError:
        return None








def api_to_db(query_doi=None, first=None, last=None, today=False, chunk_size=None):
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
    num_so_far = 0

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

        logger.info(u"calling url: {}".format(url))
        start_time = time()
        resp = requests.get(url, headers=headers)
        logger.info(u"getting crossref response took {} seconds".format(elapsed(start_time, 2)))
        if resp.status_code != 200:
            logger.info(u"error in crossref call, status_code = {}".format(resp.status_code))
            return

        resp_data = resp.json()["message"]
        next_cursor = resp_data.get("next-cursor", None)
        if next_cursor:
            next_cursor = quote(next_cursor)

        if not resp_data["items"] or not next_cursor:
            has_more_responses = False

        for api_raw in resp_data["items"]:
            # logger.info(u":")
            api = {}
            doi = api_raw["DOI"].lower()

            # using _source key for now because that's how it came out of ES and
            # haven't switched everything over yet
            api["_source"] = build_crossref_record(api_raw)
            api["_source"]["doi"] = doi

            record = Crossref(id=doi, api=api, api_raw=api_raw)
            db.session.merge(record)
            logger.info(u"got record {}".format(record))
            records_to_save.append(record)

            if len(records_to_save) >= 100:
                safe_commit(db)
                num_so_far += len (records_to_save)
                records_to_save = []
                logger.info(u"committing.  have committed {} so far, in {} seconds, is {} per hour".format(
                    num_so_far, elapsed(start_time, 1), num_so_far/(elapsed(start_time, 1)/(60*60))))


        logger.info(u"at bottom of loop")

    # make sure to get the last ones
    logger.info(u"saving last ones")
    safe_commit(db)
    logger.info(u"done everything")






if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = api_to_db
    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first 2006-01-01)")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last 2006-01-01)")

    parser.add_argument('--query_doi', nargs="?", type=str, help="pull in one doi")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in crossref records from last 2 days")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")


    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

