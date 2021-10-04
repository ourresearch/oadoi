import argparse
from time import sleep
from time import time

from sqlalchemy import text

from app import db
from app import logger
from recordthresher.pubmed import PubmedWork
from recordthresher.pubmed_record import PubmedRecord
from util import elapsed
from util import safe_commit


class QueuePubmedRecords:
    def worker_run(self, **kwargs):
        single_id = kwargs.get("pmid", None)
        chunk_size = kwargs.get("chunk", 100)
        limit = kwargs.get("limit", None)

        if limit is None:
            limit = float("inf")

        if single_id:
            pmid = PubmedWork.query.filter(PubmedWork.pmid == single_id).scalar().pmid

            if record := PubmedRecord.from_pmid(pmid):
                db.session.merge(record)

            safe_commit(db) or logger.info("COMMIT fail")
        else:
            num_updated = 0
            start_time = time()

            while num_updated < limit:
                new_loop_start_time = time()

                pmids = self.fetch_queue_chunk(chunk_size)

                if not pmids:
                    logger.info('no queued pubmed works ready. waiting...')
                    sleep(5)
                    continue

                for pmid in pmids:
                    if record := PubmedRecord.from_pmid(pmid):
                        db.session.merge(record)

                db.session.execute(
                    text('''
                        delete from recordthresher.pubmed_record_queue q
                        using recordthresher.pubmed_works w
                        where q.started > w.created
                        and q.pmid = any(:pmids)
                    ''').bindparams(pmids=pmids)
                )

                db.session.execute(
                    text('''
                        update recordthresher.pubmed_record_queue q
                        set started = null
                        where q.pmid = any(:pmids)
                    ''').bindparams(pmids=pmids)
                )

                commit_start_time = time()
                safe_commit(db) or logger.info("commit fail")
                logger.info(f'commit took {elapsed(commit_start_time, 2)} seconds')

                num_updated += chunk_size
                logger.info(f'processed {len(pmids)} works in {elapsed(start_time, 2)} seconds')

    def fetch_queue_chunk(self, chunk_size):
        logger.info("looking for new jobs")

        queue_query = text("""
            with queue_chunk as (
                select pmid
                from recordthresher.pubmed_record_queue
                where started is null
                order by rand
                limit :chunk
                for update skip locked
            )
            update recordthresher.pubmed_record_queue q
            set started = now()
            from queue_chunk
            where q.pmid = queue_chunk.pmid
            returning q.pmid;
        """).bindparams(chunk=chunk_size)

        job_time = time()
        pmid_list = [row[0] for row in db.engine.execute(queue_query.execution_options(autocommit=True)).all()]
        logger.info(f'got {len(pmid_list)} ids, took {elapsed(job_time)} seconds')

        return pmid_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--pmid', nargs="?", type=str, help="pmid you want to update")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many pmids to update")
    parser.add_argument('--chunk', "-ch", nargs="?", default=500, type=int, help="how many pmids to update at once")

    parsed_args = parser.parse_args()

    my_queue = QueuePubmedRecords()
    my_queue.worker_run(**vars(parsed_args))
