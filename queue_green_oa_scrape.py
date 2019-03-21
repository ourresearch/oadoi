import argparse
from time import sleep
from time import time

from sqlalchemy import orm, text

import os
import logging
from app import db
from app import logger
from page import PageNew
from pub import Pub # foul magic
import endpoint # magic
import pmh_record # more magic
from queue_main import DbQueue
from util import elapsed
from util import safe_commit
from sqlalchemy.orm import make_transient
from multiprocessing import Pool


def scrape_pages(pages):
    for page in pages:
        make_transient(page)

    # free up the connection while doing net IO
    db.engine.dispose()

    pool = get_worker_pool()
    scraped_pages = pool.map(scrape_page, pages, chunksize=1)

    row_dicts = [x.__dict__ for x in scraped_pages]
    for row_dict in row_dicts:
        row_dict.pop('_sa_instance_state')

    db.session.bulk_update_mappings(PageNew, row_dicts)


def get_worker_pool():
    num_request_workers = int(os.getenv('GREEN_SCRAPE_PROCS_PER_WORKER', 10))
    return Pool(processes=num_request_workers, maxtasksperchild=10)


def scrape_page(page):
    page.scrape()
    return page

class DbQueueGreenOAScrape(DbQueue):
    def table_name(self, job_type):
        return 'page_green_scrape_queue'

    def process_name(self, job_type):
        return 'run_green_oa_scrape'

    def worker_run(self, **kwargs):
        run_class = PageNew

        single_id = kwargs.get("id", None)
        chunk_size = kwargs.get("chunk", 100)
        limit = kwargs.get("limit", None)

        if limit is None:
            limit = float("inf")

        if single_id:
            objects = [run_class.query.filter(run_class.id == single_id).first()]
            scrape_pages(objects)
        else:
            index = 0
            num_updated = 0
            start_time = time()

            while num_updated < limit:
                new_loop_start_time = time()

                objects = self.fetch_queue_chunk(chunk_size)

                if not objects:
                    sleep(5)
                    continue

                scrape_pages(objects)

                object_ids = [obj.id for obj in objects]

                finish_batch_text = u'''
                    update {queue_table} 
                    set finished = now(), started=null 
                    where id = any(:ids)'''.format(queue_table=self.table_name(None))

                finish_batch_command = text(finish_batch_text).bindparams(
                    ids=object_ids)

                db.session.execute(finish_batch_command)
                safe_commit(db)

                index += 1
                num_updated += len(objects)
                self.print_update(new_loop_start_time, chunk_size, limit, start_time, index)

    def fetch_queue_chunk(self, chunk_size):
        logger.info(u"looking for new jobs")

        text_query_pattern = """
                        with update_chunk as (
                            select id
                            from {queue_table}
                            where started is null
                            and finished is null               
                            -- handle rescraping later
                            -- order by finished asc nulls first, started, rand
                            limit {chunk_size}
                            for update skip locked
                        )
                        update {queue_table} queue_rows_to_update
                        set started=now()
                        from update_chunk
                        where update_chunk.id = queue_rows_to_update.id
                        returning update_chunk.id;
                    """
        text_query = text_query_pattern.format(
            chunk_size=chunk_size,
            queue_table=self.table_name(None)
        )

        logger.info(u"the queue query is:\n{}".format(text_query))

        job_time = time()
        row_list = db.engine.execute(text(text_query).execution_options(autocommit=True)).fetchall()
        object_ids = [row[0] for row in row_list]
        logger.info(u"got ids, took {} seconds".format(elapsed(job_time)))

        job_time = time()
        q = db.session.query(PageNew).options(
            orm.undefer('*')
        ).filter(PageNew.id.in_(object_ids))

        objects = q.all()
        logger.info(u"got page_new objects in {} seconds".format(elapsed(job_time)))

        return objects


if __name__ == "__main__":
    if os.getenv('OADOI_LOG_SQL'):
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        db.session.configure()

    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--id', nargs="?", type=str, help="id of the one thing you want to update (case sensitive)")
    parser.add_argument('--doi', nargs="?", type=str, help="id of the one thing you want to update (case insensitive)")

    parser.add_argument('--reset', default=False, action='store_true', help="do you want to just reset?")
    parser.add_argument('--run', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--status', default=False, action='store_true', help="to logger.info(the status")
    parser.add_argument('--dynos', default=None, type=int, help="scale to this many dynos")
    parser.add_argument('--logs', default=False, action='store_true', help="logger.info(out logs")
    parser.add_argument('--monitor', default=False, action='store_true', help="monitor till done, then turn off dynos")
    parser.add_argument('--kick', default=False, action='store_true', help="put started but unfinished dois back to unstarted so they are retried")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many jobs to do")
    parser.add_argument('--chunk', "-ch", nargs="?", default=100, type=int, help="how many to take off db at once")

    parsed_args = parser.parse_args()

    job_type = "normal"  # should be an object attribute
    my_queue = DbQueueGreenOAScrape()
    my_queue.parsed_vars = vars(parsed_args)
    my_queue.run_right_thing(parsed_args, job_type)
