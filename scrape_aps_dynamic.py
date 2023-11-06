import os
import time
import traceback
from argparse import ArgumentParser
from datetime import datetime
from gzip import compress
from io import BytesIO
from queue import Queue
from threading import Thread

import boto3
import requests
from bs4 import BeautifulSoup

from const import LANDING_PAGE_ARCHIVE_BUCKET
from s3_util import upload_obj, landing_page_key, get_object, get_landing_page

ZYTE_API_URL = "https://api.zyte.com/v1/extract"
ZYTE_API_KEY = os.getenv("ZYTE_API_KEY")

S3 = boto3.client('s3')

SUCCESSFUL = 0
UNNECESSARY = 0
TOTAL_SEEN = 0


def get_aps_urls():
    _filter = 'primary_location.source.host_organization:https://openalex.org/P4310320261,has_raw_affiliation_string:false,has_doi:true'
    params = {'filter': _filter,
              'cursor': '*',
              'per-page': '200',
              'select': 'primary_location,doi',
              'mailto': 'nolanmccafferty@gmail.com'}
    has_next = True
    s = requests.session()
    url = 'https://api.openalex.org/works'
    while has_next:
        r = s.get(url, params=params)
        r.raise_for_status()
        j = r.json()
        for result in j['results']:
            yield clean_doi(result['doi']), result['primary_location']['landing_page_url']

        params['cursor'] = j['meta'].get('next_cursor')
        has_next = bool(params['cursor'])


def enqueue(q: Queue):
    for doi, url in get_aps_urls():
        q.put((doi, url))


def get_dynamic_response(url):
    zyte_params = {
        "url": url,
        "browserHtml": True,
        "javascript": True,
        'actions': [
            {
                "action": "waitForSelector",
                "selector": {
                    "type": "css",
                    "value": "section.article.authors",
                    "state": "visible",
                },
            },
            {
                "action": "click",
                "selector": {"type": "css", "value": "section.article.authors"},
            },
            {
                "action": "waitForSelector",
                "selector": {
                    "type": "css",
                    "value": "section.article.authors p",
                    "state": "visible",
                },
            },
        ]
    }
    r = requests.post(ZYTE_API_URL, auth=(ZYTE_API_KEY, ''), json=zyte_params)
    r.raise_for_status()
    j = r.json()
    if j['statusCode'] == 200:
        return j['browserHtml']
    raise Exception(
        f'Bad HTTP response with Zyte API: {j["statusCode"]} - j["browserHtml"]')


def needs_rescrape(doi):
    try:
        if lp := get_landing_page(doi):
            soup = BeautifulSoup(lp, features='lxml', parser='lxml')
            return not bool(soup.select_one('section.article.authors p'))
    except Exception:
        return True
    return True


def save_responses_loop(q: Queue):
    global SUCCESSFUL
    global TOTAL_SEEN
    global UNNECESSARY
    while True:
        try:
            doi, landing_page_url = q.get(timeout=30)
            if not needs_rescrape(doi):
                UNNECESSARY += 1
                continue
            html = get_dynamic_response(landing_page_url)
            body = BytesIO(compress(html.encode()))
            key = landing_page_key(doi)
            upload_obj(LANDING_PAGE_ARCHIVE_BUCKET, key, body)
            SUCCESSFUL += 1
        except Exception as e:
            print(traceback.format_exc())
        finally:
            TOTAL_SEEN += 1


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--threads', '-dt', '-t',
                        default=1,
                        type=int,
                        help='Number of threads to use to request and save landing pages')
    args = parser.parse_args()
    env_dt = int(os.getenv('SCRAPE_APS_DYNAMIC_THREADS', 0))
    if env_dt:
        args.download_threads = env_dt
    return args


def print_stats():
    started = datetime.now()
    while True:
        now = datetime.now()
        hrs_passed = (now - started).total_seconds() / (60 * 60)
        rate = round(TOTAL_SEEN / hrs_passed, 4)
        success_pct = round(SUCCESSFUL/TOTAL_SEEN, 4) if TOTAL_SEEN else 0
        print(f'Total seen: {TOTAL_SEEN} | '
              f'Successful: {SUCCESSFUL} | '
              f'Successful %: {success_pct}% | '
              f'Unnecessary: {UNNECESSARY} | '
              f'Rate: {rate}/hr')
        time.sleep(5)


def clean_doi(doi):
    if doi.startswith('10.'):
        return doi
    return doi.split('.org/')[-1]


if __name__ == '__main__':
    args = parse_args()
    threads = []
    q = Queue(maxsize=args.threads + 1)
    Thread(target=enqueue, args=(q,), daemon=True).start()
    Thread(target=print_stats, daemon=True).start()
    for i in range(args.threads):
        t = Thread(target=save_responses_loop, args=(q,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
