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
from requests.packages.urllib3.util.retry import Retry


from app import db
from app import logger
from util import elapsed
from util import safe_commit
from util import clean_doi
from util import DelayedAdapter
from pub import Pub
from pub import add_new_pubs
from pub import build_new_pub


# data from https://archive.org/details/crossref_doi_metadata
# To update the dump, use the public API with deep paging:
# https://api.crossref.org/works?filter=from-update-date:2016-04-01&rows=1000&cursor=*
# The documentation for this feature is available at:
# https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#deep-paging-with-cursors


def is_good_file(filename):
    return "chunk_" in filename

def get_api_for_one_doi(doi):
    # needs a mailto, see https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
    headers={"Accept": "application/json", "User-Agent": "mailto:team@impactstory.org"}
    root_url_doi = "https://api.crossref.org/works?filter=doi:{doi}"
    url = root_url_doi.format(doi=doi)
    resp = requests.get(url, headers=headers)
    if resp and resp.status_code == 200:
        resp_data = resp.json()["message"]
        if resp_data["items"]:
            return resp_data["items"][0]
    return None

def add_pubs_from_dois(dois):
    new_pubs = []
    for doi in dois:
        crossref_api = get_api_for_one_doi(doi)
        new_pub = build_new_pub(doi, crossref_api)

        # hack so it gets updated soon
        new_pub.updated = datetime.datetime(1042, 1, 1)

        new_pubs.append(new_pub)

    added_pubs = add_new_pubs(new_pubs)
    return added_pubs


def add_new_pubs_from_dois(dois):
    if not dois:
        return []

    rows = db.session.query(Pub.id).filter(Pub.id.in_(dois)).all()
    dois_in_db = [row[0] for row in rows]
    dois_not_in_db = [doi for doi in dois if doi not in dois_in_db]
    added_pubs = add_pubs_from_dois(dois_not_in_db)
    return added_pubs


def api_to_db(query_doi=None, first=None, last=None, today=False, week=False, chunk_size=1000):
    i = 0
    records_to_save = []

    # needs a mailto, see https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
    headers={"Accept": "application/json", "User-Agent": "mailto:team@impactstory.org"}

    root_url_with_last = "https://api.crossref.org/works?order=desc&sort=updated&filter=from-created-date:{first},until-created-date:{last}&rows={chunk}&cursor={next_cursor}"
    root_url_no_last = "https://api.crossref.org/works?order=desc&sort=updated&filter=from-created-date:{first}&rows={chunk}&cursor={next_cursor}"
    root_url_doi = "https://api.crossref.org/works?filter=doi:{doi}"

    # but if want all changes, use "indexed" not "created" as per https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#notes-on-incremental-metadata-updates
    # root_url_with_last = "https://api.crossref.org/works?order=desc&sort=updated&filter=from-indexed-date:{first},until-indexed-date:{last}&rows={chunk}&cursor={next_cursor}"
    # root_url_no_last = "https://api.crossref.org/works?order=desc&sort=updated&filter=from-indexed-date:{first}&rows={chunk}&cursor={next_cursor}"

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

        requests_session = requests.Session()
        retries = Retry(total=2,
                    backoff_factor=0.1,
                    status_forcelist=[500, 502, 503, 504])
        requests_session.mount('http://', DelayedAdapter(max_retries=retries))
        requests_session.mount('https://', DelayedAdapter(max_retries=retries))
        resp = requests_session.get(url, headers=headers)

        resp = requests.get(url, headers=headers)
        logger.info(u"getting crossref response took {} seconds".format(elapsed(crossref_time, 2)))
        if resp.status_code != 200:
            logger.info(u"error in crossref call, status_code = {}".format(resp.status_code))
            resp = None

        if resp:
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




def save_new_dois(query_doi=None, first=None, last=None, today=False, week=False, chunk_size=1000):
    # needs a mailto, see https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
    headers={"Accept": "application/json", "User-Agent": "mailto:team@impactstory.org"}

    base_url_with_last = "https://api.crossref.org/works?filter=from-issued-date:{first},until-issued-date:{last}&rows={rows}&select=DOI&cursor={next_cursor}"

    next_cursor = "*"
    has_more_responses = True
    dois_from_api = []
    number_added = 0

    start_time = time()
    while has_more_responses:
        has_more_responses = False

        start_time = time()
        url = base_url_with_last.format(
            first=first,
            last=last,
            rows=chunk_size,
            next_cursor=next_cursor)
        logger.info(u"calling url: {}".format(url))

        resp = requests.get(url, headers=headers)
        logger.info(u"getting crossref response took {} seconds.  url: {}".format(elapsed(start_time, 2), url))
        if resp.status_code != 200:
            logger.info(u"error in crossref call, status_code = {}".format(resp.status_code))
            return number_added

        resp_data = resp.json()["message"]
        next_cursor = resp_data.get("next-cursor", None)
        if next_cursor:
            next_cursor = quote(next_cursor)
            if resp_data["items"] and len(resp_data["items"]) == chunk_size:
                has_more_responses = True

        dois_from_api = [clean_doi(api_raw["DOI"]) for api_raw in resp_data["items"]]
        added_pubs = add_new_pubs_from_dois(dois_from_api)
        if dois_from_api:
            logger.info(u"got {} dois from api".format(len(dois_from_api)))
        if added_pubs:
            logger.info(u"saved {} new pubs, including \n{}".format(
                len(added_pubs), added_pubs[-2:]))

        number_added += len(added_pubs)

        logger.info(u"loop done in {} seconds".format(elapsed(start_time, 2)))

    return number_added


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = api_to_db
    if parsed["new"]:
        function = save_new_dois


    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first 2006-01-01)")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last 2006-01-01)")

    parser.add_argument('--query_doi', nargs="?", type=str, help="pull in one doi")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in crossref records from last 2 days")
    parser.add_argument('--week', action="store_true", default=False, help="use if you want to pull in crossref records from last 7 days")

    parser.add_argument('--new', action="store_true", default=False, help="use if you want to pull in new dois")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=1000, help="how many docs to put in each POST request")


    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

