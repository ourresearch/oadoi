import argparse
import base64
import gzip
import itertools
import logging
import os
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Lock, current_thread

import pdftotext
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app import db_engine

import boto3
import redis
import requests
from bs4 import BeautifulSoup
from tenacity import stop_after_attempt, retry, \
    wait_exponential

from need_rescrape_funcs import ORGS_NEED_RESCRAPE_MAP
from pdf_util import is_pdf
from s3_util import get_object, landing_page_key, make_s3, upload_obj, \
    mute_boto_logging
from util import normalize_doi
from const import LANDING_PAGE_ARCHIVE_BUCKET
from zyte_session import ZyteSession, ZytePolicy

requests.packages.urllib3.disable_warnings()

AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET = os.environ['AWS_SECRET_ACCESS_KEY']

DIR = Path(__file__).parent
RATE_LIMITS_DIR = DIR.joinpath('rate_limits')

START = datetime.now()

TOTAL_ATTEMPTED = 0
TOTAL_ATTEMPTED_LOCK = Lock()

SUCCESS = 0
SUCCESS_LOCK = Lock()

NEEDS_RESCRAPE_COUNT = 0

TOTAL_SEEN = 0

UNPAYWALL_S3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY,
                            aws_secret_access_key=AWS_SECRET)

LAST_CURSOR = None
LAST_DOI = None

LOGGER: logging.Logger = None

REDIS = redis.Redis.from_url(os.getenv('REDIS_URL'))
REDIS_LOCK = Lock()

REFRESH_QUEUE_CHUNK_SIZE = 50


def set_cursor(filter_, cursor):
    with REDIS_LOCK:
        REDIS.set(f'publisher_scrape-{filter_}', cursor)


def get_cursor(filter_):
    with REDIS_LOCK:
        cursor = REDIS.get(f'publisher_scrape-{filter_}')
        if isinstance(cursor, bytes):
            return cursor.decode()
        return cursor


def config_logger():
    mute_boto_logging()
    global LOGGER
    LOGGER = logging.getLogger('oa_filter_scraper')
    LOGGER.setLevel(logging.DEBUG)
    # fh = logging.FileHandler(f'log_{org_id}.log', 'w')
    # fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '[%(name)s | %(asctime)s] %(levelname)s - %(message)s')
    # fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # LOGGER.addHandler(fh)
    LOGGER.addHandler(ch)
    LOGGER.propagate = False
    return LOGGER


def inc_total():
    global TOTAL_ATTEMPTED
    global TOTAL_ATTEMPTED_LOCK
    with TOTAL_ATTEMPTED_LOCK:
        TOTAL_ATTEMPTED += 1


def inc_success():
    global SUCCESS_LOCK
    global SUCCESS
    with SUCCESS_LOCK:
        SUCCESS += 1


def bad_landing_page(html):
    return any([
        b'ShieldSquare Captcha' in html,
        b'429 - Too many requests' in html,
        b'We apologize for the inconvenience' in html,
        b'<title>APA PsycNet</title>' in html,
        b'<title>Redirecting</title>' in html,
        b'Your request cannot be processed at this time' in html,
        b'/cookieAbsent' in html])


def pdf_needs_rescrape(contents: bytes):
    reader = BytesIO(contents)
    pdf = None
    try:
        pdf = list(itertools.islice(pdftotext.PDF(reader), 1))
    except Exception as e:
        pass
    if not pdf:
        return True
    # less than 100 words in PDF = rescrape
    return len(pdf[0]) < 100


def doi_needs_rescrape(obj_details, pub_id, source_id):
    if obj_details['ContentLength'] < 10000:
        return True

    body = obj_details['Body'].read()
    if body[:3] == b'\x1f\x8b\x08':
        body = gzip.decompress(body)

    if is_pdf(body):
        return pdf_needs_rescrape(body)
    pub_specific_needs_rescrape = False
    source_specific_needs_rescrape = False
    soup = BeautifulSoup(body, parser='lxml', features='lxml')
    if pub_needs_rescrape_func := ORGS_NEED_RESCRAPE_MAP.get(pub_id):
        pub_specific_needs_rescrape = pub_needs_rescrape_func(soup)
    if source_needs_rescrape_func := ORGS_NEED_RESCRAPE_MAP.get(source_id):
        source_specific_needs_rescrape = source_needs_rescrape_func(soup)
    return bad_landing_page(
        body) or pub_specific_needs_rescrape or source_specific_needs_rescrape


class RateLimitException(Exception):

    def __init__(self, doi, html):
        self.message = f'RateLimitException for {doi}'
        self.html = html
        super().__init__(self.message)


@retry(stop=stop_after_attempt(5),
       wait=wait_exponential(multiplier=1, min=4, max=30))
def get_openalex_json(url, params):
    r = requests.get(url, params=params,
                     verify=False)
    r.raise_for_status()
    j = r.json()
    return j


def enqueue_dois(_filter: str, q: Queue, resume_cursor=None, rescrape=False):
    global TOTAL_SEEN
    global NEEDS_RESCRAPE_COUNT
    global LAST_CURSOR
    seen = set()
    query = {'select': 'doi,id,primary_location',
             'mailto': 'nolanmccafferty@gmail.com',
             'per-page': '200',
             'cursor': resume_cursor if resume_cursor else '*',
             # 'sample': '100',
             'filter': _filter}
    results = True
    while results:
        j = get_openalex_json('https://api.openalex.org/works',
                              params=query)
        results = j['results']
        query['cursor'] = j['meta']['next_cursor']
        LAST_CURSOR = j['meta']['next_cursor']
        filter_total_count = j['meta']['count']
        LOGGER.debug(
            f'[*] Last cursor: {LAST_CURSOR} | Filter: {_filter} | Filter total count: {filter_total_count}')
        set_cursor(_filter, LAST_CURSOR)
        for result in results:
            TOTAL_SEEN += 1
            doi = normalize_doi(result['doi'])
            # IOP probably unnecessary source
            if doi.startswith('10.1086'):
                continue
            try:
                doi_obj = get_object(LANDING_PAGE_ARCHIVE_BUCKET,
                                     landing_page_key(result['doi']))
                pub_id = \
                    result['primary_location']['source'][
                        'host_organization'].split(
                        '/')[-1]
                source_id = \
                result['primary_location']['source']['id'].split('/')[
                    -1]
                if doi in seen:
                    continue
                if doi_obj and rescrape and not doi_needs_rescrape(doi_obj,
                                                                   pub_id,
                                                                   source_id):
                    continue
                if rescrape:
                    NEEDS_RESCRAPE_COUNT += 1
                seen.add(doi)
                q.put((doi, result['id']))
            except Exception as e:
                LOGGER.warning(f'[*] Error enqueueing doi: {doi} - {e}')


def print_stats():
    while True:
        now = datetime.now()
        hrs_running = (now - START).total_seconds() / (60 * 60)
        rate_per_hr = round(TOTAL_ATTEMPTED / hrs_running, 2)
        pct_success = round((SUCCESS / TOTAL_ATTEMPTED) * 100,
                            2) if TOTAL_ATTEMPTED > 0 else 0
        LOGGER.info(
            f'[*] Total seen: {TOTAL_SEEN} | Attempted: {TOTAL_ATTEMPTED} | Successful: {SUCCESS} | Need rescraped: {NEEDS_RESCRAPE_COUNT} | % Success: {pct_success}% | Rate: {rate_per_hr}/hr | Hrs running: {round(hrs_running, 2)} | Last DOI: {LAST_DOI} | Cursor: {LAST_CURSOR}')
        time.sleep(5)


def enqueue_dois_for_refresh(dois_chunk, conn: Connection):
    stmnt = text(
        'INSERT INTO recordthresher.refresh_queue (SELECT * FROM pub WHERE id IN :dois) ON CONFLICT (id) DO UPDATE SET in_progress = FALSE;')
    conn.execute(stmnt, dois=tuple(dois_chunk))


def enqueue_for_refresh_worker(q: Queue):
    chunk = []
    with db_engine.connect() as conn:
        while True:
            try:
                doi = q.get(timeout=5 * 60)
                chunk.append(doi)
                if len(chunk) >= REFRESH_QUEUE_CHUNK_SIZE:
                    enqueue_dois_for_refresh(chunk, conn)
                    chunk = []
            except Empty:
                if chunk:
                    enqueue_dois_for_refresh(chunk, conn)
                    chunk = []


def process_dois_worker(q: Queue, refresh_q: Queue, rescrape=False,
                        zyte_policy=None, debug=False):
    global LAST_DOI
    s3 = make_s3()
    zyte_logger = ZyteSession.make_logger(current_thread().name,
                                          logging.DEBUG if debug else logging.INFO)
    # policy = ZytePolicy(type='url', regex='10\.1016/j\.physletb', profile='api', priority=1, params=json.loads('''{"actions": [{"action": "waitForSelector", "selector": {"type": "css", "state": "visible", "value": "#show-more-btn"}}, {"action": "click", "selector": {"type": "css", "value": "#show-more-btn"}}, {"action": "waitForSelector", "timeout": 15, "selector": {"type": "css", "state": "visible", "value": "div.author-collaboration div.author-group"}}], "javascript": true, "browserHtml": true, "httpResponseHeaders": true}'''))
    s = ZyteSession(logger=zyte_logger)
    while True:
        doi, openalex_id = None, None
        try:
            doi, openalex_id = q.get(timeout=5 * 60)
            url = doi if doi.startswith('http') else f'https://doi.org/{doi}'
            r = s.get(url,
                      zyte_policies=zyte_policy if zyte_policy else None,
                      fixed_policies=True if zyte_policy else False)
            r.raise_for_status()
            html = r.content
            upload_obj(LANDING_PAGE_ARCHIVE_BUCKET,
                       landing_page_key(doi),
                       BytesIO(gzip.compress(html)), s3=s3)
            inc_success()
            LAST_DOI = doi
            refresh_q.put(doi)
            if rescrape:
                LOGGER.debug(f'[*] Successfully rescraped DOI: {doi}')
        except Empty:
            if TOTAL_ATTEMPTED > 10_000:
                break
            else:
                continue
        except Exception as e:
            msg = str(e)
            LOGGER.error(f'[!] Error processing DOI ({doi}) - {msg}')
            LOGGER.exception(e)
        finally:
            inc_total()
    LOGGER.debug('[*] Exiting process DIOs loop')


def valid_cursor(cursor):
    return b'openalex.org' in base64.standard_b64decode(cursor)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_threads", '-n',
                        dest='threads',
                        help="Number of threads to use to dequeue DOIs and fetch landing pages",
                        type=int, default=30)
    parser.add_argument("--cursor", '-c',
                        dest='cursor',
                        help="Cursor to resume paginating from (optional)",
                        type=str, default=None)
    parser.add_argument('--filter', '-f',
                        help='Filter(s) with which to paginate through OpenAlex',
                        type=str,
                        action='append',
                        required=True)
    parser.add_argument("--rescrape", '-r',
                        help="Is this a rescrape job. This will only rescrape pages that are bad/blocked pages, etc. (optional)",
                        dest='rescrape',
                        action='store_true',
                        default=False)
    parser.add_argument('--policy_id', '-pid', help='Zyte policy ID (optional)',
                        dest='policy_id',
                        default=None,
                        type=str)
    parser.add_argument('--debug', '-d',
                        help='Print debug messages from ZyteSession',
                        dest='debug',
                        default=False,
                        action='store_true')
    args = parser.parse_args()
    if len(args.filter) > 1:
        args.cursor = '*'
    if args.cursor and not valid_cursor(args.cursor):
        args.cursor = '*'
    if not args.cursor:
        args.cursor = get_cursor(args.filter)
    return args


def get_zyte_policy(pid):
    if pid is None:
        return None
    elif pid == 'proxy':
        return ZytePolicy(profile='proxy')
    elif pid == 'api':
        return ZytePolicy(profile='api', params={"httpResponseBody": True,
                                                 "httpResponseHeaders": True})
    else:
        return ZytePolicy.query.get(int(pid))


def main():
    args = parse_args()
    config_logger()
    # japan_journal_of_applied_physics = 'https://openalex.org/P4310313292'
    rescrape = args.rescrape
    zyte_policy = get_zyte_policy(args.policy_id)
    if not zyte_policy:
        LOGGER.error('Zyte policy with id {} not found'.format(args.policy_id))
        return
    cursor = args.cursor
    threads = args.threads
    q = Queue(maxsize=threads + 1)
    refresh_q = Queue(maxsize=REFRESH_QUEUE_CHUNK_SIZE + 1)
    Thread(target=print_stats, daemon=True).start()
    LOGGER.debug(f'Starting with args: {vars(args)}')
    for filter_ in args.filter:
        Thread(target=enqueue_dois,
               args=(filter_, q,),
               kwargs=dict(rescrape=rescrape, resume_cursor=cursor)).start()
    Thread(target=enqueue_for_refresh_worker, args=(refresh_q,),
           daemon=True).start()
    consumers = []
    for i in range(threads):
        if threads <= 0:
            break
        t = Thread(target=process_dois_worker, args=(q, refresh_q),
                   kwargs=dict(rescrape=args.rescrape,
                               zyte_policy=zyte_policy,
                               debug=args.debug), )
        t.start()
        consumers.append(t)
    for t in consumers:
        t.join()


if __name__ == '__main__':
    # test_url('https://iopscience.iop.org/article/10.1070/RM1989v044n02ABEH002044')
    main()
