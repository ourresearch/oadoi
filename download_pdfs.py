import json
import os
import time
from argparse import ArgumentParser
from datetime import datetime
from io import BytesIO
from queue import Queue, Empty
from threading import Thread

import boto3
import botocore
from bs4 import BeautifulSoup
from pyalex import Works
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine

from app import app, logger
from http_cache import http_get
from pdf_util import PDFVersion
from s3_util import get_landing_page, mute_boto_logging
from util import normalize_doi, openalex_works_paginate

TOTAL_ATTEMPTED = 0
SUCCESSFUL = 0
ALREADY_EXIST = 0
PDF_URL_NOT_FOUND = 0
PDF_CONTENT_NOT_FOUND = 0
INVALID_PDF_COUNT = 0
LAST_SUCCESSFUL = {}

START = datetime.now()

S3_PDF_BUCKET_NAME = os.getenv('AWS_S3_PDF_BUCKET')

OADOI_DB_ENGINE: Engine = None

CRAWLERA_PROXY = 'http://{}:@impactstory.crawlera.com:8010'.format(
    os.getenv("CRAWLERA_KEY"))
CRAWLERA_PROXIES = {'http': CRAWLERA_PROXY, 'https': CRAWLERA_PROXY}

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'DNT': '1',
    'Sec-GPC': '1',
}

PARSE_QUEUE_CHUNK_SIZE = 100
DEQUEUE_CHUNK_SIZE = 100

mute_boto_logging()

INSERT_PDF_UPDATED_INGEST_LOOP_EXITED = None


class InvalidPDFException(Exception):
    pass


def pdf_exists(key, s3):
    try:
        s3.get_object(Bucket=S3_PDF_BUCKET_NAME, Key=key)
        return True
    except botocore.exceptions.ClientError as e:
        return False


# @retry(retry=retry_if_exception_type(
#     InvalidPDFException) | retry_if_exception_type(HTTPError),
#        stop=stop_after_attempt(3), reraise=True)
def fetch_pdf(url):
    r = http_get(url, ask_slowly=True)
    # r = requests.get(url, headers=HEADERS, proxies=CRAWLERA_PROXIES, verify=False)
    r.raise_for_status()
    # content = r.content
    content = r.content_big()
    if not isinstance(content, bytes):
        content = content.encode()
    if not content.startswith(b'%PDF'):
        raise InvalidPDFException(f'Not a valid PDF document: {url}')
    return content


def download_pdf(url, key, s3):
    content = fetch_pdf(url)
    body = BytesIO(content)
    s3.upload_fileobj(body, S3_PDF_BUCKET_NAME, key)


def make_s3():
    session = boto3.session.Session()
    return session.client('s3',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv(
                              'AWS_SECRET_ACCESS_KEY'), verify=False)


def parse_pdf_content(landing_page):
    if b'%PDF-' in landing_page:
        if landing_page.startswith(b'%PDF-'):
            return landing_page
        else:
            soup = BeautifulSoup(landing_page, features='lxml', parser='lxml')
            return soup.find(
                lambda tag: tag.text.contains('%PDF-')).text.encode()
    return None


def insert_into_parse_queue(parse_doi_queue: Queue):
    global INSERT_PDF_UPDATED_INGEST_LOOP_EXITED
    INSERT_PDF_UPDATED_INGEST_LOOP_EXITED = False
    with OADOI_DB_ENGINE.connect() as conn:
        chunk = []
        while True:
            try:
                doi, version = parse_doi_queue.get()
                chunk.append((doi, version))
                if len(chunk) < PARSE_QUEUE_CHUNK_SIZE:
                    continue
                _values = ', '.join([f"('{doi}', NULL, NULL, {version})" for doi, version in chunk])
                conn.execute(text(
                    f'INSERT INTO recordthresher.pdf_update_ingest (doi, started, finished, pdf_version) VALUES {_values} ON CONFLICT(doi, pdf_version) DO NOTHING;').execution_options(
                    autocommit=True))
                chunk = []
            except Empty:
                break
            except Exception as e:
                logger.exception(e, exc_info=True)
                break
    logger.info('EXITING insert_into_parse_queue loop')
    INSERT_PDF_UPDATED_INGEST_LOOP_EXITED = True


def download_pdfs(url_q: Queue, parse_q: Queue):
    global SUCCESSFUL
    global TOTAL_ATTEMPTED
    global ALREADY_EXIST
    global LAST_SUCCESSFUL
    global PDF_CONTENT_NOT_FOUND
    global INVALID_PDF_COUNT
    s3 = make_s3()
    while True:
        doi, url, version = None, None, None
        try:
            version: PDFVersion
            doi, url, version = url_q.get(timeout=60*5)
            key = version.s3_key(doi)
            if version.valid_in_s3(doi):
                ALREADY_EXIST += 1
                continue
            if not url:
                lp = get_landing_page(doi)
                if content := parse_pdf_content(lp):
                    s3.upload_fileobj(BytesIO(content), S3_PDF_BUCKET_NAME,
                                      key)
                else:
                    url = parse_pdf_url(lp)
            if url:
                download_pdf(url, key, s3)
            else:
                PDF_CONTENT_NOT_FOUND += 1
                continue
            parse_q.put((doi, version))
            SUCCESSFUL += 1
            LAST_SUCCESSFUL = {'doi': doi, 's3_key': key}
        except Empty:
            logger.error('Timeout exceeded, exiting pdf download loop...')
            break
        except InvalidPDFException as e:
            INVALID_PDF_COUNT += 1
            logger.error(f'Invalid PDF for DOI: {doi}, {url}')
        except Exception as e:
            if doi and url:
                logger.error(f'Error downloading PDF for doi {doi}: {url}')
            logger.exception(e)
        finally:
            TOTAL_ATTEMPTED += 1


def parse_pdf_url(html):
    soup = BeautifulSoup(html, features='lxml', parser='lxml')
    if pdf_tag := soup.select_one('a[href*="pdf"]'):
        return pdf_tag.get('href')
    return None


def try_parse_pdf_url(doi):
    html = get_landing_page(doi)
    return parse_pdf_url(html)


def enqueue_from_db(url_q: Queue):
    query = f'''WITH queue as (
                SELECT * FROM pdf_save_queue WHERE in_progress = false
                LIMIT {DEQUEUE_CHUNK_SIZE}
                FOR UPDATE SKIP LOCKED
                )
                UPDATE pdf_save_queue enqueued
                SET in_progress = true
                FROM queue WHERE queue.id = enqueued.id
                RETURNING *;
                '''
    rows = True
    with OADOI_DB_ENGINE.connect() as conn:
        while rows:
            rows = conn.execute(
                text(query).execution_options(autocommit=True,
                                              autoflush=True)).all()
            for row in rows:
                url_q.put((row['id'], row['scrape_pdf_url'],
                           PDFVersion.from_version_str(row['version'])))
            if not rows:
                break
            ids = [row['id'] for row in rows]
            del_query = '''
                        DELETE FROM pdf_save_queue WHERE id in :ids
                        '''
            conn.execute(text(del_query).bindparams(ids=tuple(ids)))


def enqueue_from_api(url_q: Queue, _filter):
    page_count = 0
    for page in openalex_works_paginate(_filter, select='doi,best_oa_location,type'):
        page_count += 1
        logger.info(f'Fetched page {page_count} of API with filter {_filter}')
        for work in page:
            if pdf_url := (work.get('best_oa_location', {}) or {}).get('pdf_url'):
                doi = normalize_doi(work['doi'])
                version = PDFVersion.SUBMITTED if work.get('type') == 'preprint' else PDFVersion.PUBLISHED
                url_q.put((doi, pdf_url, version))


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--api_filter', '-f', default=False, type=str,
                        help='Enqueue PDF urls to download from API filter')
    parser.add_argument('--download_threads', '-dt', '-t',
                        default=1,
                        type=int,
                        help='Number of threads to download PDFs')
    args = parser.parse_args()
    env_dt = int(os.getenv('PDF_DOWNLOAD_THREADS', 0))
    if env_dt:
        args.download_threads = env_dt
    return args


def print_stats():
    while True:
        try:
            now = datetime.now()
            hrs_running = (now - START).total_seconds() / (60 * 60)
            rate_per_hr = round(TOTAL_ATTEMPTED / hrs_running, 2)
            success_pct = round(SUCCESSFUL / (TOTAL_ATTEMPTED - ALREADY_EXIST),
                                4) * 100 if (
                    TOTAL_ATTEMPTED - ALREADY_EXIST) else 0
            logger.info(
                f'Attempted count: {TOTAL_ATTEMPTED} | '
                f'Successful count: {SUCCESSFUL} | '
                f'Success %: {success_pct}% | '
                f'Already exist count: {ALREADY_EXIST} | '
                f'PDF url not found count: {PDF_URL_NOT_FOUND} | '
                f'Invalid PDF count: {INVALID_PDF_COUNT} | '
                f'Rate: {rate_per_hr}/hr | '
                f'Last successful: {json.dumps(LAST_SUCCESSFUL)} | '
                f'Queue parse loop exited: {INSERT_PDF_UPDATED_INGEST_LOOP_EXITED} | '
                f'Hrs running: {hrs_running}hrs')
        except Exception as e:
            logger.error(e)
        finally:
            time.sleep(5)


def main():
    global OADOI_DB_ENGINE
    args = parse_args()
    OADOI_DB_ENGINE = create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                                    pool_size=args.download_threads + 1,
                                    max_overflow=0)
    logger.info(f'Starting PDF downloader with args: {args.__dict__}')
    threads = []
    parse_q = Queue(maxsize=PARSE_QUEUE_CHUNK_SIZE)
    Thread(target=print_stats, daemon=True).start()
    Thread(target=insert_into_parse_queue, daemon=True, args=(parse_q,)).start()
    q = Queue(maxsize=args.download_threads + 1)
    if args.api_filter:
        Thread(target=enqueue_from_api, args=(q, args.api_filter),
               daemon=True).start()
    else:
        Thread(target=enqueue_from_db, args=(q,), daemon=True).start()
    for _ in range(args.download_threads):
        t = Thread(target=download_pdfs, args=(q, parse_q))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == '__main__':
    main()
