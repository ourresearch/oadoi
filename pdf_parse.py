import json
import os
import time
from argparse import ArgumentParser
from datetime import datetime
from queue import Queue, Empty
from threading import Thread, Lock
from urllib.parse import urljoin

import requests
from sqlalchemy import create_engine, text

from app import app, logger

DB_ENGINE = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
OPENALEX_PDF_PARSER_URL = os.getenv('OPENALEX_PDF_PARSER_URL')
OPENALEX_PDF_PARSER_API_KEY = os.getenv('OPENALEX_PDF_PARSER_API_KEY')

TOTAL_ATTEMPTED_LOCK = Lock()
TOTAL_ATTEMPTED = 0

SUCCESFUL_LOCK = Lock()
SUCCESSFUL = 0


def inc_attempted():
    global TOTAL_ATTEMPTED
    with TOTAL_ATTEMPTED_LOCK:
        TOTAL_ATTEMPTED += 1


def inc_successful():
    global SUCCESSFUL
    with SUCCESFUL_LOCK:
        SUCCESSFUL += 1


def enqueue_from_db_loop(pdf_doi_q: Queue):
    query = '''WITH queue as (
                SELECT * FROM recordthresher.pdf_update_ingest WHERE finished IS NULL
                LIMIT 50
                FOR UPDATE SKIP LOCKED
                )
                UPDATE recordthresher.pdf_update_ingest enqueued
                SET started = now()
                FROM queue WHERE queue.doi = enqueued.doi
                RETURNING *;
                '''
    rows = True
    while rows:
        with DB_ENGINE.connect() as conn:
            rows = conn.execute(
                text(query).execution_options(autocommit=True,
                                              autoflush=True)).all()
            for row in rows:
                pdf_doi_q.put(row['doi'])
            if not rows:
                break


def fetch_parsed_pdf_response(doi):
    url = urljoin(OPENALEX_PDF_PARSER_URL, 'parse')
    r = requests.get(url, params={'doi': doi,
                                  'api_key': OPENALEX_PDF_PARSER_API_KEY})
    r.raise_for_status()
    return r.json()


def save_grobid_response_loop(pdf_doi_q: Queue):
    with DB_ENGINE.connect() as conn:
        while True:
            doi = None
            exc = None
            try:
                doi = pdf_doi_q.get(timeout=10)
                parsed = fetch_parsed_pdf_response(doi)['message']
                conn.execute(text(
                    'UPDATE recordthresher.record SET fulltext = :fulltext WHERE doi = :doi').bindparams(
                    fulltext=parsed['fulltext'],
                    doi=doi).execution_options(autocommit=True))
                conn.execute(text(
                    'INSERT INTO recordthresher.pdf_parsed (doi, authors, abstract, "references") VALUES (:doi, :authors, :abstract, :references)').bindparams(
                    doi=doi,
                    authors=json.dumps(parsed.get('authors')),
                    abstract=parsed.get('abstract'),
                    references=json.dumps(parsed.get('references')),
                ).execution_options(autocommit=True))
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
                conn.execute(text(
                    'UPDATE recordthresher.pdf_update_ingest SET finished = now(), error = :exc WHERE doi = :doi').bindparams(
                    doi=doi, exc=exc).execution_options(autocommit=True))


def print_stats():
    start = datetime.now()
    while True:
        now = datetime.now()
        hrs_running = (now - start).total_seconds() / (60 * 60)
        rate_per_hr = round(TOTAL_ATTEMPTED / hrs_running, 2)
        success_pct = round(SUCCESSFUL * 100 / TOTAL_ATTEMPTED,
                            2) if TOTAL_ATTEMPTED else 0
        logger.info(
            f'Total attempted: {TOTAL_ATTEMPTED} | Successful: {SUCCESSFUL} | Success %: {success_pct} | Rate: {rate_per_hr}/hr')
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
    q = Queue(maxsize=args.n_threads + 1)
    Thread(target=print_stats, daemon=True).start()
    Thread(target=enqueue_from_db_loop, args=(q,), daemon=True).start()

    threads = []
    for _ in range(args.n_threads):
        t = Thread(target=save_grobid_response_loop, args=(q,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == '__main__':
    main()
