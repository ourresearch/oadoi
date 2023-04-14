import os
import re
import time
from datetime import datetime
from queue import Queue, Empty
from threading import Thread, Lock

import requests
from sqlalchemy.exc import NoResultFound

from pub import Pub
from app import app, db
import endpoint  # magic

PROCESSED_LOCK = Lock()
PROCESSED_COUNT = 0

START = datetime.now()


def put_dois_api(q: Queue):
    seen = set()
    while True:
        r = requests.get("https://api.openalex.org/works?sample=25")
        for work in r.json()["results"]:
            if work['doi'] in seen:
                print(f'Seen DOI already: {work["doi"]}')
                continue
            try:
                if not isinstance(work['doi'], str):
                    continue
                doi = re.findall(r'doi.org/(.*?)$', work['doi'])
                if not doi:
                    continue
                pub = Pub.query.filter_by(id=doi[0]).one()
                q.put(pub)
                seen.add(work["doi"])
            except NoResultFound:
                continue


def put_dois_db(q: Queue):
    page_size = 1000
    offset = 0
    results = True
    while results:
        results = Pub.query.limit(page_size).offset(offset).all()
        for result in results:
            q.put(result)
        offset += page_size


def process_pubs_loop(q: Queue):
    global PROCESSED_COUNT
    while True:
        try:
            pub = q.get(timeout=60 * 5)
            pub.create_or_update_recordthresher_record()
            db.session.commit()
            with PROCESSED_LOCK:
                PROCESSED_COUNT += 1
        except Empty:
            break
    print('Exiting process pubs loop')


def print_stats():
    while True:
        now = datetime.now()
        hrs_running = (now - START).total_seconds() / (60 * 60)
        rate_per_hr = round(PROCESSED_COUNT / hrs_running, 2)
        print(
            f'[*] Processed count: {PROCESSED_COUNT} | Rate: {rate_per_hr}/hr | Hrs running: {round(hrs_running, 2)}')
        time.sleep(5)


def main():
    n_threads = int(os.getenv('RECORDTHRESHER_REFRESH_THREADS', 1))
    q = Queue(maxsize=n_threads + 1)
    print(f'[*] Starting recordthresher refresh with {n_threads} threads')
    Thread(target=print_stats, daemon=True).start()
    with app.app_context():
        Thread(target=put_dois_api, args=(q,)).start()
        threads = []
        for _ in range(n_threads):
            t = Thread(target=process_pubs_loop, args=(q,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()


if __name__ == '__main__':
    # with app.app_context():
    #     result = Pub.query.filter_by(id='10.1007/978-981-15-8338-4_1').one()
    #     result.create_or_update_recordthresher_record()
    #     db.session.commit()
    main()
