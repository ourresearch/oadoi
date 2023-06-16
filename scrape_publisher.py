import argparse
import gzip
import os
import re
import shutil
import stat
import time
import traceback
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Lock
from urllib.parse import quote

import boto3
import requests
from urllib.parse import unquote
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import ConnectionError, Timeout, RequestException
from tenacity import stop_after_attempt, retry, \
    retry_if_exception_type, wait_exponential
import logging
import redis

from http_cache import call_requests_get, ResponseObject
from need_rescrape_funcs import ORGS_NEED_RESCRAPE_MAP

from util import normalize_doi

requests.packages.urllib3.disable_warnings()

AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET = os.environ['AWS_SECRET_ACCESS_KEY']

BUCKET_NAME = 'unpaywall-doi-landing-page'

DIR = Path(__file__).parent
RATE_LIMITS_DIR = DIR.joinpath('rate_limits')

START = datetime.now()

HEADERS = {
    # 'authority': 'iopscience.iop.org',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.8',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'sec-ch-ua': '"Chromium";v="112", "Brave";v="112", "Not:A-Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'sec-gpc': '1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
    # 'Cookie': 'cfid=dba07ecc-2c0d-48b7-92dc-5a30f9ad85a9; cftoken=0',
}

CRAWLERA_KEY = os.getenv('CRAWLERA_KEY')
CRAWLERA_PROXY = f'http://{CRAWLERA_KEY}:@impactstory.crawlera.com:8010/'

TOTAL_ATTEMPTED = 0
TOTAL_ATTEMPTED_LOCK = Lock()

SUCCESS = 0
SUCCESS_LOCK = Lock()

NEEDS_RESCRAPE_COUNT = 0

TOTAL_SEEN = 0

UNPAYWALL_S3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY,
                            aws_secret_access_key=AWS_SECRET)

LAST_CURSOR = None

LOGGER: logging.Logger = None

REDIS = redis.Redis.from_url(os.getenv('REDIS_URL'))
REDIS_LOCK = Lock()


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
    global LOGGER
    LOGGER = logging.getLogger('oa_publisher_scraper')
    LOGGER.setLevel(logging.DEBUG)
    # fh = logging.FileHandler(f'log_{org_id}.log', 'w')
    # fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s')
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


def get_doi_obj(doi):
    doi = doi.replace('/', '%2F')
    try:
        return UNPAYWALL_S3.get_object(Bucket=BUCKET_NAME, Key=doi)
    except Exception:
        return None


def bad_landing_page(html):
    return any([
        b'ShieldSquare Captcha' in html,
        b'429 - Too many requests' in html,
        b'We apologize for the inconvenience' in html,
        b'<title>APA PsycNet</title>' in html,
        b'<title>Redirecting</title>' in html,
        b'/cookieAbsent' in html])


def doi_needs_rescrape(obj_details, pub_id, source_id):
    if obj_details['ContentLength'] < 10000:
        return True

    body = obj_details['Body'].read()
    if body[:3] == b'\x1f\x8b\x08':
        body = gzip.decompress(body)
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


def parse_apa_uid(url):
    matches = re.findall('/fulltext/([\d-]+)\.html', url)
    return matches[0] if matches else None


def get_apa_uid(doi, proxy=None, cookies=None):
    doi = doi.replace('%2F', '/')
    headers = {'Accept': 'application/json, text/plain, */*',
               'Accept-Language': 'en-US,en;q=0.8', 'Cache-Control': 'no-cache',
               'Connection': 'keep-alive', 'Content-Type': 'application/json',
               'Origin': 'https://psycnet.apa.org', 'Pragma': 'no-cache',
               'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors',
               'Sec-Fetch-Site': 'same-origin', 'Sec-GPC': '1',
               'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
               'X-Requested-With': 'XMLHttpRequest',
               'sec-ch-ua': '"Brave";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
               'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"macOS"'}

    json_data = {
        'api': 'doi.record',
        'params': {
            'DOI': doi,
        },
    }
    r = requests.post('https://psycnet.apa.org/api/request/doi.record',
                      headers=headers, json=json_data,
                      proxies={'http': proxy, 'https': proxy},
                      verify=False,
                      cookies=cookies)
    if not r.ok:
        return None
    j = r.json()
    if int(j['response']['result']['numFound']) > 0:
        return j['response']['result']['doc'][0]['UID']


def get_apa_lp(uid, proxy=None, cookies=None):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        # 'Cookie': 'visid_incap_2377601=KnbjioabRvm6VIsh4cE6DSfwCWQAAAAAQUIPAAAAAABbczgwQLO9OjQhJai6iplq;\nnlbi_2377601=JhgLcxgz1n3nq0Y/RZi9EAAAAADArWi3EdtR4iz5Jg6pEZ11; PN_HOST=https%3A%2F%2Fpsycnet.apa.org; PN_RC=false;\ncsId=23169937-a138-4b1b-b1ef-a298346a5547; defaultLocale=en-US; currency=USD;\nvisid_incap_2624409=ztBThy0LR3CCTyFUHY7lyijwCWQAAAAAQUIPAAAAAACwqQrZ9JTwXfOLpH/pmwxF;\nvisid_incap_2377603=NuNoMw89SYuAihxu3zgsuynwCWQAAAAAQUIPAAAAAABoeKm/xvOTB/0OQTsGN4ru;\nnlbi_2377603=DiOEd1ktPwxhmUIxBvcEhQAAAACmt6/KSXBn1D1dlZkvyAf4; cId=e67b6bd9-491c-4f81-911f-d445c932903a;\nnlbi_2624409=zGADW2JcvH5Jy+sLzJKtcwAAAABUn0LFMq/DF5BDazGeXiOA;\nincap_ses_220_2624409=+LqdeaaB8XlATK7Sq5kNAwuoG2QAAAAA4uCTsNnU6xLsiN9D3tkk7A==;\nincap_ses_1362_2624409=76BTXuL+tBsOb8OheczmEomwG2QAAAAAfi68e8Aou0Ot0AQNPBJH3Q==;\nincap_ses_156_2624409=oxJvPdpsFHVHLNk0MToqAqqwG2QAAAAA8HhE4k/jVxxQS9Q9KsAD4w==;\nincap_ses_7223_2624409=AxS0YiJUCwuRwMW/8EA9ZJ9QHGQAAAAA2CDKcoL4OhPuxrXmNYsQkA==;\nincap_ses_1483_2377601=gIcNLIy3YzYPR05WBq2UFMFeHGQAAAAAxZU3J+fU0xsNCuwKtb4Bzg==; connect.sid=s%3AL_nsE3-SXXectRI4-\n9stJRbZC2gGNkUt.1eL6wILQWsSVR6O5A8gpKMkQQjB6w7CHbRB7jQ%2BPBTU;\nreese84=3:65xnsiEY3X7egHrC7DWIAg==:ZLC3X8rYJ8xFJIuYBgK+vw4DEMXkJ8sosmtliohk2KYjjHg4ukwVzCxDzD0xc3Sk1xrVPYlypnHDWMwE\nincap_ses_1483_2377603=XI7RYKj29DFtTE5WBq2UFMReHGQAAAAARSXxyZGY9KDl+e4X51LWIg==; cart_my_apa_org=030f3022-3211-\n4816-aa22-9b7c1a2cc18a; incap_ses_1316_2624409=IABVSS1XNFs+IglirF9DEsReHGQAAAAAs2tRBXaXumaYETKK8UeDEw==;\nPN_ACCESSTIME=1679580883286; incap_ses_490_2624409=r5wTLd0gunVUpaRCQtXMBvBeHGQAAAAA57lVFTzS+F+IPcF/RzOHIw==;\nnlbi_2377601_2147483392=qB8yQFDITyhZomkYRZi9EAAAAAC9D2pGy2PWYogRQ4AH6IGs',
        'Origin': 'https://psycnet.apa.org',
        'Pragma': 'no-cache',
        'Referer': f'https://psycnet.apa.org/fulltext/{uid}.html',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
    }

    json_data = {
        'api': 'fulltext.getHTML',
        'params': {
            'uid': uid,
        },
    }

    r = requests.post(
        'https://psycnet.apa.org/api/request/fulltext.getHTML',
        headers=headers, json=json_data,
        proxies={'http': proxy, 'https': proxy},
        verify=False,
        cookies=cookies)
    r.raise_for_status()
    return r.json()['fullText']


def is_sd_redirect(soup):
    return soup.find('title') and 'Redirecting' in soup.find(
        'title') and soup.select_one('input[name=redirectURL]')


@retry(reraise=True,
       retry=(retry_if_exception_type(
           ConnectionError) | retry_if_exception_type(
           RateLimitException) | retry_if_exception_type(Timeout)),
       stop=stop_after_attempt(5))
def get_lp_response(doi, session=None, proxy=None):
    url = doi if doi.startswith('http') else f'https://doi.org/{doi}'
    if not session:
        session = requests
    r = session.get(
        url,
        proxies={'http': proxy, 'https': proxy},
        timeout=30,
        verify=False,
        headers=HEADERS)
    soup = BeautifulSoup(r.text, parser='lxml', features='lxml')
    if is_sd_redirect(soup):
        redir_url = soup.select_one('input[name=redirectURL]')['value']
        redir_url = unquote(redir_url)
        if '/abs/' not in redir_url:
            redir_url = redir_url.replace('article/pii', 'article/abs/pii')
        return get_lp_response(redir_url, session, proxy)
    if 'citation_journal_title' in r.text:
        return r
    if r.status_code == 403 or r.status_code == 429 or (
            r.status_code == 503 and 'inderscience' in r.url):
        raise RateLimitException(doi, r.text)
    r.raise_for_status()
    if 'psycnet.apa.org' in r.url:
        r.cookies.set('csId', str(uuid.uuid4()))
        r.cookies.set('cId', str(uuid.uuid4()))
        r.cookies.set('reese84', '')
        cookies = r.cookies.get_dict()
        apa_uid = parse_apa_uid(r.url)
        if not apa_uid:
            apa_uid = get_apa_uid(doi, proxy=None, cookies=cookies)
            if not apa_uid:
                return None
        content = get_apa_lp(apa_uid, proxy=None, cookies=cookies)
        if bad_landing_page(content):
            raise RateLimitException(doi, r.text)
        return content
    else:
        content_length = r.headers.get('content-length', None)
        if content_length is None:
            content_length = len(r.content)
        content_length = int(content_length)
        if bad_landing_page(r.content) or content_length < 10000:
            raise RateLimitException(doi, r.text)
    return r


@retry(stop=stop_after_attempt(20),
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
        LOGGER.debug(f'[*] Last cursor: {LAST_CURSOR}')
        set_cursor(_filter, LAST_CURSOR)
        for result in results:
            TOTAL_SEEN += 1
            short_doi = quote(normalize_doi(result['doi']), safe="")
            # IOP probably unnecessary source
            if short_doi.startswith('10.1086'):
                continue
            doi_obj = get_doi_obj(short_doi)
            pub_id = \
                result['primary_location']['source']['host_organization'].split(
                    '/')[-1]
            source_id = result['primary_location']['source']['id'].split('/')[
                -1]
            if doi_obj and rescrape and not doi_needs_rescrape(doi_obj, pub_id,
                                                               source_id):
                continue
            if rescrape:
                NEEDS_RESCRAPE_COUNT += 1
            if short_doi in seen:
                continue
            seen.add(short_doi)
            q.put((short_doi, result['id']))


def print_stats():
    while True:
        now = datetime.now()
        hrs_running = (now - START).total_seconds() / (60 * 60)
        rate_per_hr = round(TOTAL_ATTEMPTED / hrs_running, 2)
        pct_success = round((SUCCESS / TOTAL_ATTEMPTED) * 100,
                            2) if TOTAL_ATTEMPTED > 0 else 0
        LOGGER.debug(
            f'[*] Total seen: {TOTAL_SEEN} | Attempted: {TOTAL_ATTEMPTED} | Successful: {SUCCESS} | Need rescraped: {NEEDS_RESCRAPE_COUNT} | % Success: {pct_success}% | Rate: {rate_per_hr}/hr | Hrs running: {round(hrs_running, 2)} | Cursor: {LAST_CURSOR}')
        time.sleep(5)


def process_dois(q: Queue, rescrape=False):
    session = boto3.session.Session()
    s3 = session.client('s3', aws_access_key_id=AWS_ACCESS_KEY,
                        aws_secret_access_key=AWS_SECRET)
    # cloud_session = cloudscraper.create_scraper()
    while True:
        doi, openalex_id = None, None
        try:
            doi, openalex_id = q.get(timeout=5 * 60)
            url = doi if doi.startswith('http') else f'https://doi.org/{doi}'
            r = call_requests_get(url=url, logger=LOGGER)
            if not r:
                continue
            if isinstance(r, Response):
                text = r.text
            elif isinstance(r, ResponseObject):
                text = r.content
            else:
                text = r
            html = text.encode('utf-8') if isinstance(text, str) else text
            s3.upload_fileobj(BytesIO(gzip.compress(html)),
                              BUCKET_NAME,
                              doi)
            inc_success()
            if rescrape:
                LOGGER.debug(f'[*] Successfully rescraped DOI: {doi}')
        except Empty:
            if TOTAL_ATTEMPTED > 10000:
                break
            else:
                continue
        except Exception as e:
            msg = str(e)
            # if isinstance(e, RateLimitException):
            #     if not RATE_LIMITS_DIR.exists():
            #         RATE_LIMITS_DIR.mkdir()
            #     fname = doi.replace('/', '_') + '.html'
            #     with open(str(RATE_LIMITS_DIR.joinpath(fname)), 'w') as f:
            #         f.write(e.html)

            # if not isinstance(e, RateLimitException) and not isinstance(e,
            #                                                             RequestException):
            #     msg = traceback.format_exc()
            LOGGER.error(f'[!] Error processing DOI ({doi}) - {msg}')
            LOGGER.exception(e)
        finally:
            inc_total()
    LOGGER.debug('[*] Exiting process DIOs loop')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_threads", '-n',
                        dest='threads',
                        help="Number of threads to use to dequeue DOIs and fetch landing pages",
                        type=int, default=30)
    parser.add_argument("--cursor", '-c',
                        dest='cursor',
                        help="Cursor to resume paginating from",
                        type=str, default=None)
    parser.add_argument('--filter', '-f',
                        help='Filter with which to paginate through OpenAlex',
                        type=str, required=True)
    parser.add_argument("--rescrape", '-r', help="Is this a rescrape job",
                        dest='rescrape',
                        action='store_true',
                        default=False)
    args = parser.parse_args()
    if not args.cursor:
        args.cursor = get_cursor(args.filter)
    return args


def main():
    args = parse_args()
    config_logger()
    # japan_journal_of_applied_physics = 'https://openalex.org/P4310313292'
    rescrape = args.rescrape
    cursor = args.cursor
    filter_ = args.filter
    threads = args.threads
    q = Queue(maxsize=threads * 2)
    Thread(target=print_stats, daemon=True).start()
    LOGGER.debug(f'Starting with args: {vars(args)}')
    Thread(target=enqueue_dois,
           args=(filter_, q,),
           kwargs=dict(rescrape=rescrape, resume_cursor=cursor)).start()
    consumers = []
    for i in range(threads):
        if threads <= 0:
            break
        t = Thread(target=process_dois, args=(q,),
                   kwargs=dict(rescrape=args.rescrape), )
        t.start()
        consumers.append(t)
    for t in consumers:
        t.join()


if __name__ == '__main__':
    # test_url('https://iopscience.iop.org/article/10.1070/RM1989v044n02ABEH002044')
    main()
