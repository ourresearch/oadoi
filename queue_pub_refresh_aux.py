import argparse
import logging
import os
from time import sleep
from time import time

from sqlalchemy import orm, text

from app import db
from app import logger
from queue_main import DbQueue
from util import elapsed
from util import safe_commit

from pub import Pub # foul magic
import endpoint # magic
import pmh_record # more magic


class DbQueuePubRefreshAux(DbQueue):
    def table_name(self, job_type):
        return 'pub_refresh_queue_aux'

    def process_name(self, job_type):
        return 'run_aux_pub_refresh'

    def worker_run(self, **kwargs):
        chunk_size = kwargs.get("chunk", 100)
        limit = kwargs.get("limit", None)
        queue_no = kwargs.get("queue", 0)

        if limit is None:
            limit = float("inf")

        index = 0
        num_updated = 0
        start_time = time()

        while num_updated < limit:
            new_loop_start_time = time()

            objects = self.fetch_queue_chunk(chunk_size, queue_no)

            if not objects:
                sleep(5)
                continue

            for o in objects:
                o.refresh()

            finish_batch_text = u'''
                update {queue_table}
                set finished = now(), started = null, priority = null
                where id = any(:ids)'''.format(queue_table=self.table_name(None))

            finish_batch_command = text(finish_batch_text).bindparams(
                ids=[o.id for o in objects]
            )

            db.session.execute(finish_batch_command)

            commit_start_time = time()
            safe_commit(db) or logger.info(u"COMMIT fail")
            logger.info(u"commit took {} seconds".format(elapsed(commit_start_time, 2)))

            index += 1
            num_updated += chunk_size
            self.print_update(new_loop_start_time, len(objects), limit, start_time, index)

    def fetch_queue_chunk(self, chunk_size, queue_no):
        logger.info(u"looking for new jobs")

        text_query_pattern = u'''
            with refresh_queue as (
                select id
                from {queue_table}
                where
                    queue_no = {queue_no}
                    and started is null
                order by
                    priority desc,
                    rand
                limit {chunk_size}
                for update skip locked
            )
            update {queue_table} queue_rows_to_update
            set started = now()
            from refresh_queue
            where refresh_queue.id = queue_rows_to_update.id
            returning refresh_queue.id;
        '''

        text_query = text_query_pattern.format(
            chunk_size=chunk_size,
            queue_table=self.table_name(None),
            queue_no=queue_no
        )

        logger.info(u"the queue query is:\n{}".format(text_query))

        job_time = time()
        row_list = db.engine.execute(text(text_query).execution_options(autocommit=True)).fetchall()
        object_ids = [row[0] for row in row_list]
        logger.info(u"got {} ids, took {} seconds".format(len(object_ids), elapsed(job_time)))

        job_time = time()
        q = db.session.query(Pub).options(
            orm.undefer('*')
        ).filter(Pub.id.in_(object_ids))

        objects = q.all()
        logger.info(u"got pub objects in {} seconds".format(elapsed(job_time)))

        return objects


if __name__ == "__main__":
    if os.getenv('OADOI_LOG_SQL'):
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        db.session.configure()

    parser = argparse.ArgumentParser(description="Run stuff.")

    parser.add_argument('--run', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many jobs to do")
    parser.add_argument('--chunk', "-ch", nargs="?", default=1, type=int, help="how many to take off db at once")
    parser.add_argument('--queue', "-q", nargs="?", default=0, type=int, help="which queue to run")

    parser.add_argument('--dynos', default=None, type=int, help="don't use this option")
    parser.add_argument('--reset', default=False, action='store_true', help="don't use this option")
    parser.add_argument('--status', default=False, action='store_true', help="don't use this option")
    parser.add_argument('--logs', default=False, action='store_true', help="don't use this option")
    parser.add_argument('--monitor', default=False, action='store_true', help="don't use this option")
    parser.add_argument('--kick', default=False, action='store_true', help="don't use this option")
    parser.add_argument('--id', nargs="?", type=str, help="don't use this option")
    parser.add_argument('--doi', nargs="?", type=str, help="don't use this option")
    parser.add_argument('--method', nargs="?", type=str, default="update", help="don't use this option")

    parsed_args = parser.parse_args()

    job_type = "normal"  # should be an object attribute
    my_queue = DbQueuePubRefreshAux()
    my_queue.parsed_vars = vars(parsed_args)
    my_queue.run_right_thing(parsed_args, job_type)
