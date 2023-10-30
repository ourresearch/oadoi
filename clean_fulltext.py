import time
from datetime import datetime
from threading import Thread

from bs4 import BeautifulSoup
import os

from sqlalchemy import create_engine, text

engine = create_engine(
    os.getenv("OPENALEX_DATABASE_URL").replace('postgres://', 'postgresql://'))
conn = engine.connect()

PROCESSED_COUNT = 0

CHUNK_SIZE = 100


def print_stats():
    started = datetime.now()
    while True:
        now = datetime.now()
        hrs_passed = (now - started).total_seconds() / (60 * 60)
        rate = round(PROCESSED_COUNT / hrs_passed, 2)
        print(f'[*] Processing rate: {rate}/hr')
        time.sleep(5)


def clean_fulltext(fulltext, truncate_limit):
    soup = BeautifulSoup(fulltext, features='lxml', parser='lxml')
    cleaned = soup.get_text(separator=' ')
    return cleaned[:truncate_limit]


def update_fulltexts():
    global PROCESSED_COUNT
    stmnt = f'''
    with queue as (
        SELECT record_fulltext_truncate_queue.recordthresher_id, rf.fulltext FROM mid.record_fulltext_truncate_queue 
        JOIN mid.record_fulltext rf on record_fulltext_truncate_queue.recordthresher_id = rf.recordthresher_id
        WHERE started is FALSE 
        LIMIT {CHUNK_SIZE} FOR UPDATE SKIP LOCKED
    )
    update mid.record_fulltext_truncate_queue update_rows SET started = TRUE
    FROM queue WHERE update_rows.recordthresher_id = queue.recordthresher_id
    RETURNING queue.*;
    '''
    updates = []
    with conn.connection.cursor() as cursor:
        while True:
            try:
                rows = conn.execute(text(stmnt)).fetchall()
                if not rows:
                    break
                for row in rows:
                    recordthresher_id, fulltext = row
                    cleaned = clean_fulltext(fulltext, truncate_limit=200_000)
                    updates.append((recordthresher_id, cleaned))
                    PROCESSED_COUNT += 1
                if len(updates) > 0 and ((len(updates) % CHUNK_SIZE) == 0):
                    updates_template = ','.join(['%s'] * len(updates))
                    # updates_formatted = ', '.join(
                    #     [cursor.mogrify('(%s, %s)', update).decode() for update in
                    #      updates])
                    query = cursor.mogrify(
                        f'INSERT INTO mid.tmp_cleaned_fulltext (recordthresher_id, fulltext) VALUES {updates_template};',
                        updates)
                    cursor.execute(query.decode())
                    conn.connection.commit()
                    updates = []
            except Exception as e:
                print(e)
    conn.close()


if __name__ == '__main__':
    Thread(target=print_stats, daemon=True).start()
    update_fulltexts()
