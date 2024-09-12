import itertools
import time
import traceback
import tracemalloc
from argparse import ArgumentParser
from datetime import datetime
from queue import Queue, Empty
from threading import Thread, Lock
from typing import List
from endpoint import Endpoint #magic

from pyalex import Works, config
from sqlalchemy import text

from app import app, logger, db
from app import oa_db_engine
from pub import Pub
from util import normalize_doi, enqueue_add_things, make_do_redis_client

tracemalloc.start()

PROCESSED_LOCK = Lock()
PROCESSED_COUNT = 0

UPDATED_LOCK = Lock()
UPDATED_COUNT = 0

START = datetime.now()

SEEN_DOIS = set()
SEEN_LOCK = Lock()

DUPE_COUNT = 0

ENQUEUE_SLOW_QUEUE_CHUNK_SIZE = 100


def get_pub_by_id(pub_id):
    query = "SELECT * FROM pub WHERE id = :id"
    result = db.session.execute(text(query), {'id': pub_id}).mappings().first()
    if not result:
        return None
    mapping = dict(result)
    del mapping['doi']
    return Pub(**mapping)


def doi_seen(doi):
    global SEEN_DOIS
    global SEEN_LOCK
    with SEEN_LOCK:
        return doi in SEEN_DOIS


def add_seen_doi(doi):
    global SEEN_DOIS
    global SEEN_LOCK
    with SEEN_LOCK:
        SEEN_DOIS.add(doi)


def log_memory_snapshot():
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')

    logger.info("Top 10 lines with highest memory usage:")
    for index, stat in enumerate(top_stats[:10], 1):
        frame = stat.traceback[0]
        logger.info(
            f"{index}. {frame.filename}:{frame.lineno} - Size: {stat.size / 1024:.1f} KiB")


def print_stats(q: Queue = None):
    while True:
        now = datetime.now()
        hrs_running = (now - START).total_seconds() / (60 * 60)
        rate_per_hr = round(PROCESSED_COUNT / hrs_running, 2)
        msg = f'[*] Processed count: {PROCESSED_COUNT} | Updated count: {UPDATED_COUNT} | Encountered dupe count: {DUPE_COUNT} | Rate: {rate_per_hr}/hr | Hrs running: {round(hrs_running, 2)}'
        if q:
            msg += f' | Queue size: {q.qsize()}'
        logger.info(msg)
        # log_memory_snapshot()
        time.sleep(5)


def enqueue_slow_queue_worker(q: Queue):
    dois = []
    redis_conn = make_do_redis_client()
    with oa_db_engine.connect() as oa_db_conn:
        while True:
            try:
                doi = q.get()
                dois.append(doi)
                if len(dois) >= ENQUEUE_SLOW_QUEUE_CHUNK_SIZE:
                    enqueue_add_things(list(set(dois)), oa_db_conn,
                                       priority=-1,
                                       fast_queue_priority=-1,
                                       redis_conn=redis_conn)
                    dois.clear()
            except Empty:
                return


def refresh_sql(slow_queue_q: Queue, chunk_size=10):
    global PROCESSED_COUNT, UPDATED_COUNT
    query = f'''WITH queue as (
            SELECT * FROM recordthresher.refresh_queue WHERE in_progress = false
            LIMIT {chunk_size}
            FOR UPDATE SKIP LOCKED
            )
            UPDATE recordthresher.refresh_queue enqueued
            SET in_progress = true
            FROM queue WHERE queue.id = enqueued.id
            RETURNING *
            '''
    rows = True
    with app.app_context():
        while rows:
            rows = db.session.execute(text(query)).all()
            for r in rows:
                processed, updated = False, False
                mapping = dict(r._mapping).copy()
                del mapping['in_progress']
                method_name = mapping.get('method',
                                          'create_or_update_recordthresher_record')
                del mapping['method']
                pub = get_pub_by_id(mapping.get('id'))
                if not pub:
                    print(f'Pub not found for DOI: {mapping.get("id")}')
                    continue
                try:
                    method = getattr(pub, method_name)
                    if method_name == 'create_or_update_recordthresher_record':
                        all_records = mapping.get('all_records', True)
                        if method(all_records):
                            db.session.commit()
                    else:
                        if method():
                            db.session.commit()
                    slow_queue_q.put(r.id)
                    updated = True
                    processed = True
                except Exception as e:
                    db.session.rollback()
                    logger.exception(
                        f'[!] Error updating record: {r.id} - {e}')
                    logger.exception(traceback.format_exc())
                finally:
                    del_query = "DELETE FROM recordthresher.refresh_queue WHERE id = :id_"
                    db.session.execute(text(del_query).bindparams(id_=r.id).execution_options(autocommit=True))
                    if processed:
                        with PROCESSED_LOCK:
                            PROCESSED_COUNT += 1
                    if updated:
                        with UPDATED_LOCK:
                            UPDATED_COUNT += 1


def filter_string_to_dict(oa_filter_str):
    items = oa_filter_str.split(',')
    d = {}
    for item in items:
        k, v = item.split(':', maxsplit=1)
        d[k] = v
    return d


def enqueue_from_api(oa_filters):
    config.email = 'team@ourresearch.org'
    for oa_filter in oa_filters:
        print(f'[*] Starting to enqueue using OA filter: {oa_filter}')
        d = filter_string_to_dict(oa_filter)
        pager = iter(Works().filter(**d).paginate(per_page=200, n_max=None))
        i = 0
        while True:
            try:
                page = next(pager)
                dois = tuple(
                    {normalize_doi(work['doi'], True) for work in page})
                dois = [doi for doi in dois if doi]
                stmnt = '''
                    INSERT INTO recordthresher.refresh_queue(id, in_progress, method)
                    SELECT UNNEST(:dois), FALSE, 'create_or_update_recordthresher_record'
                    ON CONFLICT(id) DO UPDATE 
                    SET in_progress = FALSE, 
                        method = 'create_or_update_recordthresher_record';
                '''
                db.session.execute(text(stmnt), {'dois': dois})
                db.session.commit()
                print(
                    f'[*] Inserted {200 * (i + 1)} into refresh queue from filter - {oa_filter}')
            except StopIteration:
                break
            finally:
                i += 1


def chunker(seq: List, size: int):
    """Yield successive n-sized chunks from seq."""
    it = iter(seq)
    return iter(lambda: list(itertools.islice(it, size)), [])


def enqueue_from_txt(path):
    with open(path) as f:
        contents = f.read()
        dois = list(
            set([line.split('doi.org/')[-1] if line.startswith('http') else line
                 for line in contents.splitlines()]))
        dois = tuple(normalize_doi(doi, True) for doi in dois)
        dois = [doi for doi in dois if doi]
        stmnt = '''
            INSERT INTO recordthresher.refresh_queue(id, in_progress, method)
            SELECT UNNEST(:dois), FALSE, 'create_or_update_recordthresher_record'
            ON CONFLICT(id) DO UPDATE 
            SET in_progress = FALSE, 
                method = 'create_or_update_recordthresher_record';
        '''
        for i, chunk in enumerate(chunker(dois, 1000), 1):
            db.session.execute(text(stmnt).bindparams(dois=chunk))
            db.session.commit()
            print(f'Enqueued {len(chunk)*(i + 1)} DOIs from {path}')
    print(f'Enqueued {len(dois)} DOIs from {path}')


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--txt',
                        help='Path to txt file to refresh DOIs (one per line)',
                        type=str)
    parser.add_argument('--n_threads', '-n', help='Number of threads to use',
                        type=int, default=10)
    parser.add_argument('--oa_filters', '-f', action='append',
                        help='OpenAlex filters from which to enqueue works to recordthresher refresh')

    return parser.parse_args()


def split(a, n):
    k, m = divmod(len(a), n)
    return (a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))


if __name__ == '__main__':
    args = parse_args()
    if args.txt:
        enqueue_from_txt(args.txt)
    if args.oa_filters:
        threads = []
        # pub_ids = list(set(args.enqueue_pub))
        # base_oa_filter = 'type:journal-article,has_doi:true,has_raw_affiliation_string:false,publication_date:>2015-01-01'
        chunks = split(list(set(args.oa_filters)), args.n_threads)
        for chunk in chunks:
            t = Thread(target=enqueue_from_api, args=(chunk,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
    else:
        slow_queue_q = Queue(maxsize=args.n_threads)
        Thread(target=enqueue_slow_queue_worker, args=(slow_queue_q,),
               daemon=True).start()
        Thread(target=print_stats, daemon=True).start()
        threads = []
        for _ in range(args.n_threads):
            t = Thread(target=refresh_sql, args=(slow_queue_q,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()
