import argparse
from time import sleep
from time import time

from sqlalchemy import text

from app import db
from app import logger
from pmh_record import PmhRecord
from recordthresher.record_maker import PmhRecordMaker
from util import elapsed
from util import safe_commit


import endpoint  # magic


class QueuePmhRTRecord:
    def worker_run(self, **kwargs):
        single_id = kwargs.get("pmh_id", None)
        chunk_size = kwargs.get("chunk", 100)
        limit = kwargs.get("limit", None)

        if limit is None:
            limit = float("inf")

        if single_id:
            pmh = PmhRecord.query.filter(PmhRecord.id == single_id).scalar()

            if record := PmhRecordMaker.make_record(pmh):
                db.session.merge(record)

            safe_commit(db) or logger.info("COMMIT fail")
        else:
            num_updated = 0

            while num_updated < limit:
                start_time = time()

                pmh_ids = self.fetch_queue_chunk(chunk_size)

                if not pmh_ids:
                    logger.info('no queued pmh records ready to update. waiting...')
                    sleep(5)
                    continue

                for pmh_id in pmh_ids:
                    if pmh := PmhRecord.query.filter(PmhRecord.id == pmh_id).scalar():
                        if record := PmhRecordMaker.make_record(pmh):
                            db.session.merge(record)

                db.session.execute(
                    text('''
                        delete from recordthresher.pmh_record_queue q
                        where q.pmh_id = any(:pmh_ids)
                    ''').bindparams(pmh_ids=pmh_ids)
                )

                commit_start_time = time()
                safe_commit(db) or logger.info("commit fail")
                logger.info(f'commit took {elapsed(commit_start_time, 2)} seconds')

                num_updated += chunk_size
                logger.info(f'processed {len(pmh_ids)} PMH records in {elapsed(start_time, 2)} seconds')

    def fetch_queue_chunk(self, chunk_size):
        logger.info("looking for new jobs")

        queue_query = text("""
            with queue_chunk as (
                select pmh_id
                from recordthresher.pmh_record_queue
                where started is null
                order by rand
                limit :chunk
                for update skip locked
            )
            update recordthresher.pmh_record_queue q
            set started = now()
            from queue_chunk
            where q.pmh_id = queue_chunk.pmh_id
            returning q.pmh_id;
        """).bindparams(chunk=chunk_size)

        job_time = time()
        pmh_id_list = [row[0] for row in db.engine.execute(queue_query.execution_options(autocommit=True)).all()]
        logger.info(f'got {len(pmh_id_list)} ids, took {elapsed(job_time)} seconds')

        return pmh_id_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--pmh_id', nargs="?", type=str, help="pmh_id you want to update the RT record for")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many records to update")
    parser.add_argument('--chunk', "-ch", nargs="?", default=100, type=int, help="how many records to update at once")

    parsed_args = parser.parse_args()

    my_queue = QueuePmhRTRecord()
    my_queue.worker_run(**vars(parsed_args))
