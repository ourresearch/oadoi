import json
import time
from datetime import datetime
from threading import Thread

from sqlalchemy import text

from recordthresher.pdf_record import PDFRecord
from app import oa_db_engine, db

CHUNK_SIZE = 1000

INSERTED = 0

stmnt = f'''
    with queue as (
        SELECT q.doi, parsed.authors, parsed.abstract, parsed.references FROM public.tmp_pdf_recordthresher_queue q JOIN public.pdf_parsed parsed ON q.doi = parsed.doi
        WHERE in_progress is FALSE
        LIMIT {CHUNK_SIZE} FOR UPDATE SKIP LOCKED
    )
    update public.tmp_pdf_recordthresher_queue update_rows SET in_progress = TRUE
    FROM queue WHERE update_rows.doi = queue.doi
    RETURNING queue.*;
    '''


def insert_pdf_records_loop():
    global INSERTED
    with oa_db_engine.connect() as conn:
        while True:
            rows = conn.execute(stmnt).fetchall()
            if not rows:
                break
            pdf_records = []
            for row in rows:
                doi, authors, abstract, references = row
                pdf_records.append(PDFRecord(doi=doi,
                                             authors=json.dumps(authors),
                                             abstract=abstract,
                                             citations=json.dumps(references)))
            db.session.bulk_save_objects(pdf_records)
            db.session.execute(text('DELETE FROM tmp_pdf_recordthresher_queue WHERE doi IN :dois'),
                               params={'dois': tuple([record.doi for record in pdf_records])})
            db.session.commit()
            INSERTED += CHUNK_SIZE


def print_stats():
    start = datetime.now()
    while True:
        now = datetime.now()
        hrs_elapsed = (now - start).total_seconds()/(60*60)
        rate = round(INSERTED/hrs_elapsed, 2) if hrs_elapsed > 0 else 0
        print(f'Inserted - {INSERTED} | Rate - {rate}/hr')
        time.sleep(5)


if __name__ == '__main__':
    Thread(target=print_stats, daemon=True).start()
    insert_pdf_records_loop()