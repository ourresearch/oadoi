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
from util import clean_doi
from pub import Pub
from pub import add_new_pubs
from pub import build_new_pub


# data from https://archive.org/details/crossref_doi_metadata
# To update the dump, use the public API with deep paging:
# http://api.crossref.org/works?filter=from-update-date:2016-04-01&rows=1000&cursor=*
# The documentation for this feature is available at:
# https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#deep-paging-with-cursors


def is_good_file(filename):
    return "chunk_" in filename



def api_to_db(query_doi=None, first=None, last=None, today=False, week=False, chunk_size=1000):
    i = 0
    records_to_save = []

    headers={"Accept": "application/json", "User-Agent": "impactstory.org"}

    root_url_with_last = "http://api.crossref.org/works?order=desc&sort=updated&filter=from-created-date:{first},until-created-date:{last}&rows={chunk}&cursor={next_cursor}"
    root_url_no_last = "http://api.crossref.org/works?order=desc&sort=updated&filter=from-created-date:{first}&rows={chunk}&cursor={next_cursor}"
    root_url_doi = "http://api.crossref.org/works?filter=doi:{doi}"

    # but if want all changes, use "indexed" not "created" as per https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#notes-on-incremental-metadata-updates
    # root_url_with_last = "http://api.crossref.org/works?order=desc&sort=updated&filter=from-indexed-date:{first},until-indexed-date:{last}&rows={chunk}&cursor={next_cursor}"
    # root_url_no_last = "http://api.crossref.org/works?order=desc&sort=updated&filter=from-indexed-date:{first}&rows={chunk}&cursor={next_cursor}"

    next_cursor = "*"
    has_more_responses = True
    num_pubs_added_so_far = 0
    pubs_this_chunk = []

    if week:
        last = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        first = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    elif today:
        last = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        first = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    if not first:
        first = "2016-04-01"

    start_time = time()

    while has_more_responses:
        if query_doi:
            url = root_url_doi.format(doi=query_doi)
        else:
            if last:
                url = root_url_with_last.format(first=first,
                                                last=last,
                                                next_cursor=next_cursor,
                                                chunk=chunk_size)
            else:
                # query is much faster if don't have a last specified, even if it is far in the future
                url = root_url_no_last.format(first=first,
                                              next_cursor=next_cursor,
                                              chunk=chunk_size)

        logger.info(u"calling url: {}".format(url))
        crossref_time = time()
        resp = requests.get(url, headers=headers)
        logger.info(u"getting crossref response took {} seconds".format(elapsed(crossref_time, 2)))
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
            loop_time = time()

            doi = clean_doi(api_raw["DOI"])
            my_pub = build_new_pub(doi, api_raw)

            # hack so it gets updated soon
            my_pub.updated = datetime.datetime(1042, 1, 1)

            pubs_this_chunk.append(my_pub)

            if len(pubs_this_chunk) >= 100:
                added_pubs = add_new_pubs(pubs_this_chunk)
                logger.info(u"added {} pubs, loop done in {} seconds".format(len(added_pubs), elapsed(loop_time, 2)))
                num_pubs_added_so_far += len(added_pubs)

                # if new_pubs:
                #     id_links = ["http://api.oadoi.org/v2/{}".format(my_pub.id) for my_pub in new_pubs[0:5]]
                #     logger.info(u"last few ids were {}".format(id_links))

                pubs_this_chunk = []
                loop_time = time()

        logger.info(u"at bottom of loop")

    # make sure to get the last ones
    logger.info(u"saving last ones")
    added_pubs = add_new_pubs(pubs_this_chunk)
    num_pubs_added_so_far += len(added_pubs)
    logger.info(u"Added >>{}<< new crossref dois on {}, took {} seconds".format(
        num_pubs_added_so_far, datetime.datetime.now().isoformat()[0:10], elapsed(start_time, 2)))






if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = api_to_db
    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first 2006-01-01)")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last 2006-01-01)")

    parser.add_argument('--query_doi', nargs="?", type=str, help="pull in one doi")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in crossref records from last 2 days")
    parser.add_argument('--week', action="store_true", default=False, help="use if you want to pull in crossref records from last 7 days")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=1000, help="how many docs to put in each POST request")


    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

