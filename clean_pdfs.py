import gzip
import os
import re
from io import BytesIO
from queue import Queue, Empty
from threading import Thread
from urllib.parse import unquote

import boto3
from requests import HTTPError
from sqlalchemy import create_engine, text
from tenacity import retry_if_exception_type, stop_after_attempt, retry

from app import app
from http_cache import http_get

S3_PDF_BUCKET_NAME = os.getenv('AWS_S3_PDF_BUCKET')

DB_ENGINE = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])


def make_s3():
    session = boto3.session.Session()
    return session.client('s3',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv(
                              'AWS_SECRET_ACCESS_KEY'))


class InvalidPDFException(Exception):
    pass


@retry(retry=retry_if_exception_type(
    InvalidPDFException) | retry_if_exception_type(HTTPError),
       stop=stop_after_attempt(5), reraise=True)
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


def compress_and_reupload(key, body, s3):
    body = gzip.compress(body)
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
                if body.startswith(b'%PDF') and not zipped:
                    compress_and_reupload(key, body, s3)
                else:
                    # object is not PDF, need to attempt to re-download
                    row = conn.execute(text(
                        'SELECT scrape_pdf_url FROM pub WHERE id = :doi').bindparams(
                        doi=key_to_doi(key))).one()
                    download_pdf(row['scrape_pdf_url'], key, s3)
                    # TODO: if pdf re-download fails, delete current object from S3
            except Empty:
                break


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


def main():
    n_threads = 1
    q = Queue(maxsize=n_threads + 1)
    Thread(target=enqueue_s3_keys, args=(q,)).start()

    threads = []
    for _ in range(n_threads):
        t = Thread(target=process_pdf_keys, args=(q,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == '__main__':
    main()
