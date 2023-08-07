import gzip
import os
import re
import time
from argparse import ArgumentParser
from datetime import datetime
from io import BytesIO
from queue import Queue, Empty
from threading import Thread, Lock
from urllib.parse import unquote

import boto3
from requests import HTTPError
from sqlalchemy import create_engine, text
from tenacity import retry_if_exception_type, stop_after_attempt, retry

from app import app, logger
from http_cache import http_get

S3_PDF_BUCKET_NAME = os.getenv('AWS_S3_PDF_BUCKET')

DB_ENGINE = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])

DECOMPRESSED_LOCK = Lock()
REDOWNLOADED_LOCK = Lock()
FAILED_AND_DELETED_LOCK = Lock()
TOTAL_ATTEMPTED_LOCK = Lock()
OK_LOCK = Lock()
EMPTY_PDF_URL_LOCK = Lock()

DECOMPRESSED = 0
REDOWNLOADED = 0
FAILED_AND_DELETED = 0
TOTAL_ATTEMPTED = 0
OK_COUNT = 0
EMPTY_PDF_URL = 0


def inc_decompressed():
    global DECOMPRESSED
    with DECOMPRESSED_LOCK:
        DECOMPRESSED += 1


def inc_redownloaded():
    global REDOWNLOADED
    with REDOWNLOADED_LOCK:
        REDOWNLOADED += 1


def inc_failed():
    global FAILED_AND_DELETED
    with FAILED_AND_DELETED_LOCK:
        FAILED_AND_DELETED += 1


def inc_total():
    global TOTAL_ATTEMPTED
    with TOTAL_ATTEMPTED_LOCK:
        TOTAL_ATTEMPTED += 1


def inc_ok():
    global OK_COUNT
    with OK_LOCK:
        OK_COUNT += 1


def inc_empty_pdf_url():
    global EMPTY_PDF_URL
    with EMPTY_PDF_URL_LOCK:
        EMPTY_PDF_URL += 1


def make_s3():
    session = boto3.session.Session()
    return session.client('s3',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv(
                              'AWS_SECRET_ACCESS_KEY'))


class InvalidPDFException(Exception):
    pass


# @retry(retry=retry_if_exception_type(
#     InvalidPDFException) | retry_if_exception_type(HTTPError),
#        stop=stop_after_attempt(3), reraise=True)
def fetch_pdf(url):
    r = http_get(url)
    r.raise_for_status()
    if not r.content.startswith(b'%PDF'):
        raise InvalidPDFException(f'Not a valid PDF document: {url}')
    return r


def download_pdf(url, key, s3):
    r = fetch_pdf(url)
    s3.upload_fileobj(BytesIO(gzip.compress(r.content)), S3_PDF_BUCKET_NAME,
                      key)


def upload(key, body, s3):
    s3.upload_fileobj(BytesIO(body), S3_PDF_BUCKET_NAME,
                      key)


def key_to_doi(key):
    return re.sub('.pdf$', '', unquote(key))


def process_pdf_keys(q: Queue):
    s3 = make_s3()
    with DB_ENGINE.connect() as conn:
        while True:
            try:
                key = q.get(timeout=15)
                obj_details = s3.get_object(Bucket=S3_PDF_BUCKET_NAME, Key=key)
                body = obj_details['Body'].read()
                zipped = False
                if body[:3] == b'\x1f\x8b\x08':
                    body = gzip.decompress(body)
                    zipped = True
                if body.startswith(b'%PDF') and zipped:
                    upload(key, body, s3)
                    inc_decompressed()
                elif not body.startswith(b'%PDF'):
                    # object is not PDF, need to attempt to re-download
                    row = conn.execute(text(
                        'SELECT scrape_pdf_url FROM pub WHERE id = :doi').bindparams(
                        doi=key_to_doi(key))).one()
                    if row['scrape_pdf_url'] is None:
                        inc_empty_pdf_url()
                        continue
                    download_pdf(row['scrape_pdf_url'], key, s3)
                    inc_redownloaded()
                else:
                    inc_ok()
            except Empty:
                break
            except (HTTPError, InvalidPDFException) as e:
                s3.delete_object(Bucket=S3_PDF_BUCKET_NAME, Key=key)
                inc_failed()
                logger.error(
                    f'Unable to re-download PDF: {row["scrape_pdf_url"]} - {e}\nDeleted key {key}')
            except Exception as e:
                logger.exception(f'Error with key: {key}', exc_info=True)
            finally:
                inc_total()


def print_stats():
    start = datetime.now()
    while True:
        now = datetime.now()
        hrs_running = (now - start).total_seconds() / (60 * 60)
        rate_per_hr = round(TOTAL_ATTEMPTED / hrs_running, 2)
        redownloaded_pct = round(REDOWNLOADED / TOTAL_ATTEMPTED,
                                 4) * 100 if TOTAL_ATTEMPTED else 0
        logger.info(
            f'Attempted count: {TOTAL_ATTEMPTED} | '
            f'Ok count : {OK_COUNT} | '
            f'Redownloaded count: {REDOWNLOADED} | '
            f'Redownloaded %: {redownloaded_pct}% | '
            f'Deleted count: {FAILED_AND_DELETED} | '
            f'Decompressed count: {DECOMPRESSED} | '
            f'Empty PDF URL count: {EMPTY_PDF_URL} | '
            f'Rate: {rate_per_hr}/hr | '
            f'Hrs running: {hrs_running}hrs')
        time.sleep(5)


def enqueue_s3_keys(q: Queue):
    s3 = make_s3()
    has_more = True
    count = 0
    cont_token = None
    while has_more:
        kwargs = {'Bucket': S3_PDF_BUCKET_NAME}
        if cont_token:
            kwargs['ContinuationToken'] = cont_token
        page = s3.list_objects_v2(**kwargs)
        count += page['MaxKeys']
        has_more = bool(page.get('NextContinuationToken'))
        cont_token = page.get('NextContinuationToken')
        for obj in page['Contents']:
            q.put(obj['Key'])


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--threads', '-t',
                        default=10,
                        type=int,
                        help='Number of threads to process PDF keys')
    args = parser.parse_args()
    env_dt = int(os.getenv('PDF_CLEAN_THREADS', 0))
    if env_dt:
        args.download_threads = env_dt
    return args


def main():
    args = parse_args()

    q = Queue(maxsize=args.threads + 1)
    Thread(target=print_stats, daemon=True).start()
    Thread(target=enqueue_s3_keys, args=(q,)).start()

    threads = []
    for _ in range(args.threads):
        t = Thread(target=process_pdf_keys, args=(q,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == '__main__':
    main()
