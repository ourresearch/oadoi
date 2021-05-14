import argparse
import datetime
import os
from time import time
from urllib.parse import quote

import requests
from requests.packages.urllib3.util.retry import Retry

from app import db
from app import logger
from app import logging
from pub import Pub
from pub import add_new_pubs
from pub import build_new_pub
from util import DelayedAdapter
from util import elapsed
from util import normalize_doi
from util import safe_commit


# data from https://archive.org/details/crossref_doi_metadata
# To update the dump, use the public API with deep paging:
# https://api.crossref.org/works?filter=from-update-date:2016-04-01&rows=1000&cursor=*
# The documentation for this feature is available at:
# https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#deep-paging-with-cursors


def is_good_file(filename):
    return "chunk_" in filename


def get_api_for_one_doi(doi):
    # needs a mailto, see https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
    headers={"Accept": "application/json", "User-Agent": "mailto:dev@ourresearch.org"}
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


def add_pubs_or_update_crossref(pubs):
    if not pubs:
        return []

    pubs_by_id = dict((p.id, p) for p in pubs)

    existing_pub_ids = set([
        id_tuple[0] for id_tuple in db.session.query(Pub.id).filter(Pub.id.in_(list(pubs_by_id.keys()))).all()
    ])

    pubs_to_add = [p for p in pubs if p.id not in existing_pub_ids]
    pubs_to_update = [p for p in pubs if p.id in existing_pub_ids]

    if pubs_to_add:
        logger.info("adding {} pubs".format(len(pubs_to_add)))
        db.session.add_all(pubs_to_add)

    if pubs_to_update:
        row_dicts = [{'id': p.id, 'crossref_api_raw_new': p.crossref_api_raw_new} for p in pubs_to_update]
        logger.info("updating {} pubs".format(len(pubs_to_update)))
        db.session.bulk_update_mappings(Pub, row_dicts)

    safe_commit(db)
    return pubs_to_add


def get_response_page(url):
    # needs a mailto, see https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
    headers = {"Accept": "application/json", "User-Agent": "mailto:dev@ourresearch.org"}

    requests_session = requests.Session()

    retries = Retry(total=10, backoff_factor=1, status_forcelist=[413, 429, 500, 502, 503, 504])
    requests_session.mount('http://', DelayedAdapter(max_retries=retries))
    requests_session.mount('https://', DelayedAdapter(max_retries=retries))

    r = requests_session.get(url, headers=headers, timeout=(180, 180))

    return r


def get_dois_and_data_from_crossref(query_doi=None, first=None, last=None, today=False, week=False, offset_days=0, chunk_size=1000, get_updates=False):


    root_url_doi = "https://api.crossref.org/works?filter=doi:{doi}"

    if get_updates:
        root_url_with_last = "https://api.crossref.org/works?order=desc&sort=indexed&filter=from-index-date:{first},until-index-date:{last}&rows={chunk}&cursor={next_cursor}"
        root_url_no_last = "https://api.crossref.org/works?order=desc&sort=indexed&filter=from-index-date:{first}&rows={chunk}&cursor={next_cursor}"
    else:
        root_url_with_last = "https://api.crossref.org/works?order=desc&sort=updated&filter=from-created-date:{first},until-created-date:{last}&rows={chunk}&cursor={next_cursor}"
        root_url_no_last = "https://api.crossref.org/works?order=desc&sort=updated&filter=from-created-date:{first}&rows={chunk}&cursor={next_cursor}"

    next_cursor = "*"
    has_more_responses = True
    num_pubs_added_so_far = 0
    pubs_this_chunk = []

    if week:
        last = (datetime.date.today() + datetime.timedelta(days=1))
        first = (datetime.date.today() - datetime.timedelta(days=7))
    elif today:
        last = (datetime.date.today() + datetime.timedelta(days=1))
        first = (datetime.date.today() - datetime.timedelta(days=2))

    if not first:
        first = datetime.date(2016, 4, 1)

    last = last and last - datetime.timedelta(days=offset_days)
    first = first and first - datetime.timedelta(days=offset_days)

    start_time = time()

    insert_pub_fn = add_pubs_or_update_crossref if get_updates else add_new_pubs

    while has_more_responses:
        if query_doi:
            url = root_url_doi.format(doi=query_doi)
        else:
            if last:
                url = root_url_with_last.format(first=first.isoformat(),
                                                last=last.isoformat(),
                                                next_cursor=next_cursor,
                                                chunk=chunk_size)
            else:
                # query is much faster if don't have a last specified, even if it is far in the future
                url = root_url_no_last.format(first=first.isoformat(),
                                              next_cursor=next_cursor,
                                              chunk=chunk_size)

        logger.info("calling url: {}".format(url))
        crossref_time = time()

        resp = get_response_page(url)
        logger.info("getting crossref response took {} seconds".format(elapsed(crossref_time, 2)))
        if resp.status_code != 200:
            logger.info("error in crossref call, status_code = {}".format(resp.status_code))
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

                doi = normalize_doi(api_raw["DOI"])
                my_pub = build_new_pub(doi, api_raw)

                # hack so it gets updated soon
                my_pub.updated = datetime.datetime(1042, 1, 1)

                pubs_this_chunk.append(my_pub)

                if len(pubs_this_chunk) >= 100:
                    added_pubs = insert_pub_fn(pubs_this_chunk)
                    logger.info("added {} pubs, loop done in {} seconds".format(len(added_pubs), elapsed(loop_time, 2)))
                    num_pubs_added_so_far += len(added_pubs)

                    pubs_this_chunk = []

        logger.info("at bottom of loop")

    # make sure to get the last ones
    logger.info("saving last ones")
    added_pubs = insert_pub_fn(pubs_this_chunk)
    num_pubs_added_so_far += len(added_pubs)
    logger.info("Added >>{}<< new crossref dois on {}, took {} seconds".format(
        num_pubs_added_so_far, datetime.datetime.now().isoformat()[0:10], elapsed(start_time, 2)))


# this one is used for catch up.  use the above function when we want all weekly dois
def scroll_through_all_dois(query_doi=None, first=None, last=None, today=False, week=False, chunk_size=1000):
    # needs a mailto, see https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
    headers = {"Accept": "application/json", "User-Agent": "mailto:dev@ourresearch.org"}

    if first:
        base_url = "https://api.crossref.org/works?filter=from-created-date:{first},until-created-date:{last}&rows={rows}&select=DOI&cursor={next_cursor}"
    else:
        base_url = "https://api.crossref.org/works?filter=until-created-date:{last}&rows={rows}&select=DOI&cursor={next_cursor}"

    next_cursor = "*"
    has_more_responses = True
    number_added = 0

    while has_more_responses:
        has_more_responses = False

        start_time = time()
        url = base_url.format(
            first=first,
            last=last,
            rows=chunk_size,
            next_cursor=next_cursor)
        logger.info("calling url: {}".format(url))

        resp = requests.get(url, headers=headers)
        logger.info("getting crossref response took {} seconds.  url: {}".format(elapsed(start_time, 2), url))
        if resp.status_code != 200:
            logger.info("error in crossref call, status_code = {}".format(resp.status_code))
            return number_added

        resp_data = resp.json()["message"]
        next_cursor = resp_data.get("next-cursor", None)
        if next_cursor:
            next_cursor = quote(next_cursor)
            if resp_data["items"] and len(resp_data["items"]) == chunk_size:
                has_more_responses = True

        dois_from_api = [normalize_doi(api_raw["DOI"]) for api_raw in resp_data["items"]]
        added_pubs = add_new_pubs_from_dois(dois_from_api)
        if dois_from_api:
            logger.info("got {} dois from api".format(len(dois_from_api)))
        if added_pubs:
            logger.info("{}: saved {} new pubs, including {}".format(
                first, len(added_pubs), added_pubs[-2:]))

        number_added += len(added_pubs)

        logger.info("loop done in {} seconds".format(elapsed(start_time, 2)))

    return number_added


def date_str(s):
    return datetime.datetime.strptime(s, '%Y-%m-%d').date()


if __name__ == "__main__":
    if os.getenv('OADOI_LOG_SQL'):
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        db.session.configure()

    parser = argparse.ArgumentParser(description="Run stuff.")

    function = get_dois_and_data_from_crossref

    parser.add_argument('--first', nargs="?", type=date_str, help="first filename to process (example: --first 2006-01-01)")
    parser.add_argument('--last', nargs="?", type=date_str, help="last filename to process (example: --last 2006-01-01)")

    parser.add_argument('--query_doi', nargs="?", type=str, help="pull in one doi")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in crossref records from last 2 days")
    parser.add_argument('--week', action="store_true", default=False, help="use if you want to pull in crossref records from last 7 days")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=1000, help="how many docs to put in each POST request")
    parser.add_argument('--offset_days', nargs="?", type=int, default=0, help="advance the import date range by this many days")

    parser.add_argument('--get-updates', action="store_true", default=False, help="use if you want to get updates within the date range, not just new records")

    parsed = parser.parse_args()

    logger.info("calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

