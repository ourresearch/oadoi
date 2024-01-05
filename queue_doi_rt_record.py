import argparse
import datetime
from threading import Thread
from time import sleep
from time import time

from sqlalchemy import text

from app import db
from app import logger
from pub import Pub
from recordthresher.record import RecordthresherParentRecord
from recordthresher.record_maker import CrossrefRecordMaker, PmhRecordMaker
from recordthresher.record_maker.parseland_record_maker import ParselandRecordMaker
from util import elapsed
from util import safe_commit

import endpoint  # magic

PROCESSED = 0


def print_stats():
    start = datetime.datetime.now()
    while True:
        now = datetime.datetime.now()
        hrs_running = (now - start).total_seconds() / (60 * 60)
        rate_hr = round(PROCESSED/hrs_running, 2)
        logger.info(f'[*] Processing rate: {rate_hr}/hr')
        sleep(5)


class QueueDoiRtRecord:
    def worker_run(self, **kwargs):
        global PROCESSED
        single_id = kwargs.get("doi", None)
        chunk_size = kwargs.get("chunk", 100)
        limit = kwargs.get("limit", None)

        if limit is None:
            limit = float("inf")

        if single_id:
            pub = Pub.query.get(single_id)

            if record := CrossrefRecordMaker.make_record(pub):
                db.session.merge(record)
                PROCESSED += 1

            safe_commit(db) or logger.info("COMMIT fail")
        else:
            num_updated = 0

            while num_updated < limit:
                start_time = time()

                dois = self.fetch_queue_chunk(chunk_size)

                if not dois:
                    logger.info(
                        'no queued DOI records ready to update. waiting...')
                    sleep(5)
                    continue

                for doi in dois:
                    logger.info(f'making RecordThresher record for DOI {doi}')
                    if pub := Pub.query.get(doi):
                        if record := CrossrefRecordMaker.make_record(pub):
                            db.session.merge(record)
                            PROCESSED += 1

                            if pl_record := ParselandRecordMaker.make_record(self, update_existing=False):
                                db.session.merge(pl_record)

                            secondary_records = PmhRecordMaker.make_secondary_repository_responses(record)
                            for secondary_record in secondary_records:
                                db.session.merge(secondary_record)
                                db.session.merge(
                                    RecordthresherParentRecord(
                                        record_id=secondary_record.id,
                                        parent_record_id=record.id
                                    )
                                )

                db.session.execute(
                    text('''
                        delete from recordthresher.doi_record_queue q
                        where q.doi = any(:dois)
                    ''').bindparams(dois=dois)
                )

                commit_start_time = time()
                safe_commit(db) or logger.info("commit fail")
                logger.info(
                    f'commit took {elapsed(commit_start_time, 2)} seconds')

                num_updated += chunk_size
                logger.info(
                    f'processed {len(dois)} DOI records in {elapsed(start_time, 2)} seconds')

    def fetch_queue_chunk(self, chunk_size):
        logger.info("looking for new jobs")

        queue_query = text("""
            with queue_chunk as (
                select doi
                from recordthresher.doi_record_queue
                where started is null
                order by updated desc nulls last, rand
                limit :chunk
                for update skip locked
            )
            update recordthresher.doi_record_queue q
            set started = now()
            from queue_chunk
            where q.doi = queue_chunk.doi
            returning q.doi;
        """).bindparams(chunk=chunk_size)

        job_time = time()
        doi_list = [row[0] for row in db.engine.execute(
            queue_query.execution_options(autocommit=True)).all()]
        logger.info(
            f'got {len(doi_list)} DOIs, took {elapsed(job_time)} seconds')

        return doi_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--doi', nargs="?", type=str,
                        help="doi you want to update the RT record for")
    parser.add_argument('--limit', "-l", nargs="?", type=int,
                        help="how many records to update")
    parser.add_argument('--chunk', "-ch", nargs="?", default=100, type=int,
                        help="how many records to update at once")

    parsed_args = parser.parse_args()

    my_queue = QueueDoiRtRecord()
    Thread(target=print_stats, daemon=True).start()
    my_queue.worker_run(**vars(parsed_args))
