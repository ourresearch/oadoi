import base64
import gzip
import json
import logging
import os
import time
from argparse import ArgumentParser
from datetime import datetime
from io import BytesIO
from queue import Queue, Empty
from threading import Thread, Lock
from urllib.parse import urljoin

import boto3
import botocore
import requests
from bs4 import BeautifulSoup
from requests import HTTPError
from sqlalchemy import create_engine, text
from tenacity import retry, stop_after_attempt, retry_if_exception_type

from app import app, logger
from const import GROBID_XML_BUCKET
from pdf_util import PDFVersion

OADOI_DB_ENGINE = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
OPENALEX_DB_ENGINE = create_engine(os.getenv('OPENALEX_DATABASE_URL'))
OPENALEX_PDF_PARSER_URL = os.getenv('OPENALEX_PDF_PARSER_URL')
OPENALEX_PDF_PARSER_API_KEY = os.getenv('OPENALEX_PDF_PARSER_API_KEY')

TOTAL_ATTEMPTED_LOCK = Lock()
TOTAL_ATTEMPTED = 0

SUCCESFUL_LOCK = Lock()
SUCCESSFUL = 0

SEEN = set()
SEEN_LOCK = Lock()

DUPE_COUNT = 0
DUPE_COUNT_LOCK = Lock()

ALREADY_PARSED_COUNT = 0
ALREADY_PARSED_LOCK = Lock()

libs_to_mum = [
    'boto',
    'boto3',
    'botocore',
    's3transfer'
]

for lib in libs_to_mum:
    logging.getLogger(lib).setLevel(logging.CRITICAL)


def inc_already_parsed():
    global ALREADY_PARSED_COUNT
    with ALREADY_PARSED_LOCK:
        ALREADY_PARSED_COUNT += 1


def add_to_seen(doi):
    with SEEN_LOCK:
        SEEN.add(doi)


def doi_is_seen(doi):
    with SEEN_LOCK:
        return doi in SEEN


def inc_dupe_count():
    global DUPE_COUNT
    with DUPE_COUNT_LOCK:
        DUPE_COUNT += 1


def inc_attempted():
    global TOTAL_ATTEMPTED
    with TOTAL_ATTEMPTED_LOCK:
        TOTAL_ATTEMPTED += 1


def inc_successful():
    global SUCCESSFUL
    with SUCCESFUL_LOCK:
        SUCCESSFUL += 1


def make_s3():
    session = boto3.session.Session()
    return session.client('s3',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv(
                              'AWS_SECRET_ACCESS_KEY'))


def grobid_pdf_exists(key, s3):
    try:
        s3.get_object(Bucket=GROBID_XML_BUCKET, Key=key)
        return True
    except botocore.exceptions.ClientError as e:
        return False


def enqueue_from_db_loop(pdf_doi_q: Queue):
    query = '''WITH queue as (
                SELECT * FROM recordthresher.pdf_update_ingest WHERE started IS NULL
                LIMIT 50
                FOR UPDATE SKIP LOCKED
                )
                UPDATE recordthresher.pdf_update_ingest enqueued
                SET started = now()
                FROM queue WHERE queue.doi = enqueued.doi
                RETURNING *;
                '''
    rows = True
    with OADOI_DB_ENGINE.connect() as conn:
        while rows:
            rows = conn.execute(
                text(query).execution_options(autocommit=True,
                                              autoflush=True)).all()
            for row in rows:
                pdf_doi_q.put((row['doi'], PDFVersion.from_version_str(row['pdf_version'])))
            if not rows:
                break


@retry(stop=stop_after_attempt(3), reraise=True,
       retry=retry_if_exception_type(HTTPError))
def fetch_parsed_pdf_response(doi, version: PDFVersion):
    url = urljoin(OPENALEX_PDF_PARSER_URL, 'parse')
    r = requests.get(url, params={'doi': doi,
                                  'api_key': OPENALEX_PDF_PARSER_API_KEY,
                                  'version': version.value})
    r.raise_for_status()
    return r.json()


def decompress_raw(raw):
    return gzip.decompress(base64.decodebytes(raw.encode())).decode()


def process_db_statements_loop(db_q: Queue):
    oadoi_conn = OADOI_DB_ENGINE.connect()
    openalex_conn = OPENALEX_DB_ENGINE.connect()
    conns = {'OADOI': oadoi_conn, 'OPENALEX': openalex_conn}
    while True:
        try:
            stmnt, conn_name, force_commit = db_q.get(timeout=120)
            conns[conn_name].execute(stmnt)
        except Empty:
            logger.debug('Exiting process_db_statements_loop')
            break
        except Exception as e:
            logger.exception("Error executing db statement", exc_info=True)
    oadoi_conn.close()
    openalex_conn.close()


def save_grobid_response_loop(pdf_doi_q: Queue, db_q: Queue):
    s3 = make_s3()
    known_keys = {'authors', 'fulltext', 'references', 'raw', 'abstract'}
    while True:
        doi = None
        exc = None
        try:
            doi, version = pdf_doi_q.get(timeout=20)
            if doi_is_seen(doi):
                inc_dupe_count()
                continue
            add_to_seen(doi)
            if version.grobid_in_s3(doi):
                inc_already_parsed()
                continue
            parsed = fetch_parsed_pdf_response(doi, version)['message']
            soup = BeautifulSoup(parsed['fulltext'], parser='lxml', features='lxml')
            stmnt = text(
                '''INSERT INTO mid.record_fulltext (recordthresher_id, fulltext) SELECT r.id, :fulltext FROM (SELECT id FROM ins.recordthresher_record WHERE doi = :doi AND record_type = 'crossref_doi') r ON CONFLICT(recordthresher_id) DO UPDATE SET fulltext = :fulltext;''').bindparams(
                    fulltext=soup.get_text(separator=' '),
                    doi=doi)
            db_q.put((stmnt, 'OPENALEX', False))
            other_obj = {}
            for k, v in parsed.items():
                if k not in known_keys:
                    other_obj[k] = v
            stmnt = text(
                'INSERT INTO recordthresher.pdf_parsed (doi, authors, abstract, "references", other) VALUES (:doi, :authors, :abstract, :references, :other) ON CONFLICT (doi) DO NOTHING').bindparams(
                doi=doi,
                authors=json.dumps(parsed.get('authors')),
                abstract=parsed.get('abstract'),
                references=json.dumps(parsed.get('references')),
                other=json.dumps(other_obj)
            )
            db_q.put((stmnt, 'OADOI', False))
            if raw := parsed.get('raw'):
                gzipped = base64.decodebytes(raw.encode())
                s3.upload_fileobj(BytesIO(gzipped), Key=version.grobid_s3_key(doi),
                                  Bucket=GROBID_XML_BUCKET)
            inc_successful()
        except Empty:
            break
        except Exception as e:
            exc = e
            if doi:
                logger.exception(
                    f'Error fetching GROBID response for DOI: {doi}',
                    exc_info=True)
            else:
                logger.exception('Error', exc_info=True)
        finally:
            inc_attempted()
            stmnt = text(
                'UPDATE recordthresher.pdf_update_ingest SET finished = now(), error = :exc WHERE doi = :doi').bindparams(
                doi=doi, exc=str(exc))
            db_q.put((stmnt, 'OADOI', False))


def print_stats():
    start = datetime.now()
    while True:
        now = datetime.now()
        hrs_running = (now - start).total_seconds() / (60 * 60)
        rate_per_hr = round(TOTAL_ATTEMPTED / hrs_running, 2)
        success_pct = round(SUCCESSFUL * 100 / TOTAL_ATTEMPTED,
                            2) if TOTAL_ATTEMPTED else 0
        logger.info(
            f'Total attempted: {TOTAL_ATTEMPTED} | Successful: {SUCCESSFUL} | Success %: {success_pct} | Duplicates: {DUPE_COUNT} | Already parsed: {ALREADY_PARSED_COUNT} | Rate: {rate_per_hr}/hr')
        time.sleep(5)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--n_threads', '-t', type=int, default=10,
                        help='Number of threads to fetch GROBID responses with')
    args = parser.parse_args()
    env_n_threads = os.getenv('PDF_PARSE_N_THREADS')
    if env_n_threads:
        args.n_threads = int(env_n_threads)
    return args


def main():
    args = parse_args()
    logger.info(f'Starting with {args.n_threads} threads')
    q = Queue(maxsize=args.n_threads + 1)
    db_q = Queue(maxsize=args.n_threads + 1)
    Thread(target=print_stats, daemon=True).start()
    Thread(target=enqueue_from_db_loop, args=(q,), daemon=True).start()
    Thread(target=process_db_statements_loop, args=(db_q,), daemon=True).start()

    threads = []
    for _ in range(args.n_threads):
        t = Thread(target=save_grobid_response_loop, args=(q, db_q))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == '__main__':
    main()
