import os
import re
import time
from argparse import ArgumentParser
from datetime import datetime
from gzip import decompress
from io import BytesIO
from queue import Queue, Empty
from threading import Thread
from urllib.parse import quote

import boto3
import botocore
import requests
from bs4 import BeautifulSoup
from pyalex import Works
from sqlalchemy import text

from app import app, db, logger
import endpoint  # magic
from http_cache import http_get

TOTAL_ATTEMPTED = 0
SUCCESSFUL = 0
ALREADY_EXIST = 0
PDF_URL_NOT_FOUND = 0
PDF_CONTENT_NOT_FOUND = 0

START = datetime.now()

S3_PDF_BUCKET_NAME = os.getenv('AWS_S3_PDF_BUCKET')


def normalize_doi(doi):
    if doi.startswith('http'):
        return re.findall(r'doi.org/(.*?)$', doi)[0]
    return doi


def pdf_exists(key, s3):
    try:
        s3.get_object(Bucket=S3_PDF_BUCKET_NAME, Key=key)
        return True
    except botocore.exceptions.ClientError as e:
        return False


def download_pdf(url, key, s3):
    r = http_get(url)
    s3.upload_fileobj(BytesIO(r.content), S3_PDF_BUCKET_NAME, key)


def make_s3():
    session = boto3.session.Session()
    return session.client('s3',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv(
                              'AWS_SECRET_ACCESS_KEY'))


def parse_pdf_content(landing_page):
    if b'%PDF-' in landing_page:
        if landing_page.startswith(b'%PDF-'):
            return landing_page
        else:
            soup = BeautifulSoup(landing_page, features='lxml', parser='lxml')
            return soup.find(
                lambda tag: tag.text.contains('%PDF-')).text.encode()
    return None


def download_pdfs(url_q: Queue):
    global SUCCESSFUL
    global TOTAL_ATTEMPTED
    global ALREADY_EXIST
    global PDF_CONTENT_NOT_FOUND
    s3 = make_s3()
    while True:
        doi, url = None, None
        try:
            doi, url = url_q.get(timeout=15)
            key = f'{quote(doi, safe="")}.pdf'
            if pdf_exists(key, s3):
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
            SUCCESSFUL += 1
        except Empty:
            logger.error('Timeout exceeded, exiting pdf download loop...')
            break
        except Exception as e:
            if doi and url:
                logger.error(f'Error downloading PDF for doi {doi}: {url}')
            logger.exception(e)
        finally:
            TOTAL_ATTEMPTED += 1


def get_landing_page(doi):
    url = f"https://api.unpaywall.org/doi_page/{doi}"
    r = requests.get(url)
    if not r.ok:
        return None
    return decompress(r.content)


def parse_pdf_url(html):
    soup = BeautifulSoup(html, features='lxml', parser='lxml')
    if pdf_tag := soup.select_one('a[href*="pdf"]'):
        return pdf_tag.get('href')
    return None


def try_parse_pdf_url(doi):
    html = get_landing_page(doi)
    return parse_pdf_url(html)


def enqueue_from_db(url_q: Queue):
    offset = 0
    limit = 100
    with app.app_context():
        while True:
            query = '''SELECT * FROM pub WHERE scrape_pdf_url IS NOT NULL LIMIT :limit OFFSET :offset'''
            rows = db.session.execute(
                text(query).bindparams(offset=offset, limit=limit)).all()
            for row in rows:
                url_q.put((row['id'], row['scrape_pdf_url']))
            if not rows:
                break
            offset += limit


def enqueue_from_api(url_q: Queue):
    pager = Works().filter(is_oa=True, has_doi=True).paginate(per_page=200)
    global PDF_URL_NOT_FOUND
    for page in pager:
        for work in page:
            pdf_url = work['best_oa_location']['pdf_url']
            url_q.put((work['doi'], pdf_url))


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--api', '-a', default=False,
                        action='store_true',
                        help='Enqueue PDF urls to download from API rather than database (default)')
    parser.add_argument('--download_threads', '-dt',
                        default=50,
                        type=int,
                        help='Number of threads to download PDFs')
    args = parser.parse_args()
    env_dt = os.getenv('PDF_DOWNLOAD_THREADS')
    if env_dt:
        args.download_threads = env_dt
    return args


def print_stats():
    while True:
        now = datetime.now()
        hrs_running = (now - START).total_seconds() / (60 * 60)
        rate_per_hr = round(TOTAL_ATTEMPTED / hrs_running, 2)
        success_pct = round(SUCCESSFUL / TOTAL_ATTEMPTED,
                            4) * 100 if TOTAL_ATTEMPTED else 0
        logger.info(
            f'Attempted count: {TOTAL_ATTEMPTED} | '
            f'Successful count: {SUCCESSFUL} | '
            f'Success %: {success_pct}% | '
            f'Already exist count: {ALREADY_EXIST} | '
            f'PDF url not found count: {PDF_URL_NOT_FOUND} | '
            f'Rate: {rate_per_hr}/hr | '
            f'Hrs running: {hrs_running}hrs')
        time.sleep(5)


def main():
    args = parse_args()
    threads = []
    Thread(target=print_stats, daemon=True).start()
    q = Queue(maxsize=args.download_threads + 1)
    if args.api:
        Thread(target=enqueue_from_api, args=(q,), daemon=True).start()
    else:
        Thread(target=enqueue_from_db, args=(q,), daemon=True).start()
    for _ in range(args.download_threads):
        t = Thread(target=download_pdfs, args=(q,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == '__main__':
    main()
