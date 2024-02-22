# -*- coding: utf-8 -*-

DESCRIPTION = """query arXiv oai pmh api and add new records to track"""

import sys, os, time
from typing import List
from pathlib import Path
from datetime import datetime, timedelta
from timeit import default_timer as timer
import requests
import backoff
from bs4 import BeautifulSoup as Soup

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from app import db
from tracking.models import ArxivTrack, OpenAlexRecordTrack


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_time=240)
@backoff.on_predicate(backoff.expo, lambda x: x.status_code >= 429, max_time=240)
def make_request(url, params=None):
    if params is None:
        return requests.get(url)
    else:
        return requests.get(url, params=params)


def query_openalex_api(arxiv_id) -> str:
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"locations.landing_page_url:http://arxiv.org/abs/{arxiv_id}|https://arxiv.org/abs/{arxiv_id}",
        "mailto": "dev@ourresearch.org",
        "select": "id",
    }
    r = make_request(url, params=params)
    ids = [item["id"] for item in r.json()["results"]]
    return ",".join(ids)


def get_arxiv_ids_from_arxiv_api() -> List[str]:
    now = datetime.utcnow()
    from_date = now - timedelta(days=1)
    from_date_str = from_date.isoformat()[:10]
    until_date_str = now.isoformat()[:10]

    arxiv_ids = []
    url = "https://export.arxiv.org/oai2"
    first_request_params = {
        "verb": "ListRecords",
        "from": from_date_str,
        "until": until_date_str,
        "metadataPrefix": "arXivRaw",
    }
    logger.info(
        f"querying arxiv api: {url} using from: {from_date_str} until: {until_date_str}"
    )

    r = make_request(url, params=first_request_params)
    num_requests = 1
    logger.info(f"{num_requests} requests to arXiv api made so far")

    while True:
        soup = Soup(r.text, "xml")
        records = soup.findAll("record")
        resumption_token = soup.find("resumptionToken")

        for record in records:
            arxivId = record.find("id").text
            # openalex_id = query_openalex_api(arxivId)
            # if not openalex_id:
            #     arxiv_ids.append(arxivId)
            arxiv_ids.append(arxivId)

        if not resumption_token:
            break
        else:
            token = resumption_token.text
            params = {
                "verb": "ListRecords",
                "resumptionToken": token,
            }
            r = make_request(url, params=params)
            num_requests += 1
            logger.info(f"{num_requests} requests to arXiv api made so far")
    logger.info(
        f"done querying arxiv api. made {num_requests} requests. retrieved {len(arxiv_ids)} records."
    )
    return arxiv_ids


def exists_in_openalex_tracking(arxiv_id):
    return db.session.query(OpenAlexRecordTrack).filter_by(arxiv_id=arxiv_id).all()


def main(args):
    arxiv_ids = get_arxiv_ids_from_arxiv_api()
    now = datetime.utcnow()
    num_added = 0
    num_already_tracked = 0
    num_already_in_openalex = 0
    for arxiv_id_short in arxiv_ids:
        arxiv_id = f"arXiv:{arxiv_id_short}"
        existing = db.session.query(ArxivTrack).filter_by(arxiv_id=arxiv_id).all()
        if existing:
            # don't add
            num_already_tracked += 1
            logger.debug(
                f"{arxiv_id} -- skipping because already being tracked in oadoi"
            )
            continue
        openalex_id = query_openalex_api(arxiv_id_short)
        if openalex_id:
            # don't add
            num_already_in_openalex += 1
            logger.debug(f"{arxiv_id} -- skipping because already in openalex api")
            continue

        # add record to track
        rec = ArxivTrack(arxiv_id=arxiv_id, created_at=now, active=True)
        db.session.add(rec)

        # add openalex record to track
        if not exists_in_openalex_tracking(arxiv_id):
            openalex_rec = OpenAlexRecordTrack(
                arxiv_id=arxiv_id,
                created_at=now,
                note="arxiv investigation",
                origin="arxiv_oai_pmh",
            )
            db.session.add(openalex_rec)

        num_added += 1
    db.session.commit()
    logger.info(
        f"added {num_added} records to track in oadoi and openalex_db. skipped {num_already_tracked} that were already being tracked. skipped {num_already_in_openalex} that were already in the OpenAlex API"
    )


if __name__ == "__main__":
    total_start = timer()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(name)s.%(lineno)d %(levelname)s : %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    logger.info(" ".join(sys.argv))
    logger.info("{:%Y-%m-%d %H:%M:%S}".format(datetime.now()))
    logger.info("pid: {}".format(os.getpid()))
    import argparse

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--debug", action="store_true", help="output debugging info")
    global args
    args = parser.parse_args()
    if args.debug:
        root_logger.setLevel(logging.DEBUG)
        logger.debug("debug mode is on")
    main(args)
    total_end = timer()
    logger.info(
        "all finished. total time: {}".format(format_timespan(total_end - total_start))
    )
