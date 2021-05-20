import argparse
import datetime
import os
from time import time, sleep
from urllib.parse import quote

import requests
from requests.packages.urllib3.util.retry import Retry

from app import db
from app import logger
from app import logging
from util import DelayedAdapter
from util import elapsed
from util import normalize_doi


class CrossrefCrawl(db.Model):
    started = db.Column(db.DateTime, primary_key=True)
    last_request = db.Column(db.DateTime)
    cursor = db.Column(db.Text)
    cursor_tries = db.Column(db.Integer)
    done = db.Column(db.Boolean)


class CrossrefCrawlDoi(db.Model):
    id = db.Column(db.BigInteger, primary_key=True)  # identity column in pg
    crawl_time = db.Column(db.DateTime)
    doi = db.Column(db.Text)


def get_response_page(url):
    # needs a mailto, see https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
    headers = {"Accept": "application/json", "User-Agent": "mailto:dev@ourresearch.org"}

    requests_session = requests.Session()

    retries = Retry(total=10, backoff_factor=1, status_forcelist=[413, 429, 500, 502, 503, 504])
    requests_session.mount('http://', DelayedAdapter(max_retries=retries))
    requests_session.mount('https://', DelayedAdapter(max_retries=retries))

    try:
        return requests_session.get(url, headers=headers, timeout=(180, 180))
    except Exception:
        return None


def crawl_crossref(page_delay=None, page_length=None):
    # see if there's an unfinished crawl
    active_crawl = None
    unfinished_crawl = CrossrefCrawl.query.filter(CrossrefCrawl.done.is_(None)).scalar()

    if unfinished_crawl:
        logger.info('found an unfinished crawl starting at {}'.format(unfinished_crawl.started))

        # see if it's still running
        last_request = unfinished_crawl.last_request
        if last_request is None or last_request > datetime.datetime.utcnow() - datetime.timedelta(hours=2):
            logger.info(
                'aborting, unfinished crawl still looks active. started: {}, last request {}'.format(
                    unfinished_crawl.started,
                    unfinished_crawl.last_request
                )
            )
            return

        # see if we should resume it
        if unfinished_crawl.cursor_tries < 5:
            # resume it
            active_crawl = unfinished_crawl
        else:
            # kill it
            unfinished_crawl.done = False
            db.session.commit()

    if not active_crawl:
        logger.info('beginning a new crawl')
        active_crawl = CrossrefCrawl(started=datetime.datetime.utcnow(), cursor='*', cursor_tries=0)
        db.session.add(active_crawl)
        db.session.commit()

    root_url = 'https://api.crossref.org/works?cursor={next_cursor}'
    if page_length:
        root_url = root_url + '&rows={}'.format(page_length)

    has_more_responses = True

    while has_more_responses:
        url = root_url.format(next_cursor=active_crawl.cursor)
        logger.info("calling url: {}".format(url))

        active_crawl.last_request = datetime.datetime.utcnow()
        db.session.commit()

        crossref_time = time()
        resp = get_response_page(url)
        logger.info("getting crossref response took {} seconds".format(elapsed(crossref_time, 2)))

        if not resp or resp.status_code != 200:
            # abort, try agan later
            logger.info("error in crossref call, status_code = {}".format(resp and resp.status_code))
            active_crawl.cursor_tries += 1
            active_crawl.last_request = None
            db.session.commit()
            return
        else:
            # save DOIs
            resp_data = resp.json()["message"]

            page_dois = []
            for api_raw in resp_data["items"]:
                doi = normalize_doi(api_raw["DOI"])
                if doi:
                    page_dois.append({'crawl_time': active_crawl.started, 'doi': doi})

            # update cursor
            next_cursor = resp_data.get("next-cursor", None)
            if next_cursor:
                next_cursor = quote(next_cursor)

            if not resp_data["items"] or not next_cursor:
                has_more_responses = False
                active_crawl.done = True
            else:
                active_crawl.cursor = next_cursor
                active_crawl.cursor_tries = 0

            if page_dois:
                db.session.bulk_insert_mappings(CrossrefCrawlDoi, page_dois)

            db.session.commit()

            logger.info('added {} dois'.format(len(page_dois)))

            if page_delay:
                logger.info('sleeping {} seconds'.format(page_delay))
                sleep(page_delay)


if __name__ == "__main__":
    if os.getenv('OADOI_LOG_SQL'):
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        db.session.configure()

    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--page-delay', nargs="?", type=int, default=20, help="many seconds to wait between page requests")
    parser.add_argument('--page-length', nargs="?", type=int, default=1000, help="many results to request per page")
    parsed = parser.parse_args()

    crawl_crossref(parsed.page_delay, parsed.page_length)


