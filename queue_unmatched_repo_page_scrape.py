import argparse
import logging
import os
from time import sleep
from time import time

from sqlalchemy import orm, text

from app import db
from app import logger
from queue_main import DbQueue
from unmatched_repo_page import UnmatchedRepoPage
from util import elapsed
from util import safe_commit

from pub import Pub  # magic
import endpoint  # magic
import pmh_record  # magic

class UnmatchedRepoPageScrape(DbQueue):
    def __init__(self, **kwargs):
        self.queue_query = self._make_queue_query()
        super(UnmatchedRepoPageScrape, self).__init__(**kwargs)

    def _make_queue_query(self):
        return text("""
            with update_page as (
                select
                    q.id, e.endpoint_id
                    from
                        endpoint_page_scrape_status e
                        join unmatched_page_scrape_queue q using (endpoint_id)
                    where
                        q.started is null
                        and e.next_scrape_start < now()
                        and (q.finished is null or q.finished < now() - interval '2 months')
                    order by e.next_scrape_start, q.finished nulls first, q.rand
                    limit 1
                    for update of q, e skip locked
            ), update_endpoint as (
                update endpoint_page_scrape_status e
                set next_scrape_start = now() + scrape_interval
                from update_page p  
                where e.endpoint_id = p.endpoint_id
            )
            update unmatched_page_scrape_queue queue_row_to_update
            set started=now()
            from update_page
            where queue_row_to_update.id = update_page.id
            returning update_page.id;
        """)

    def table_name(self, job_type):
        return 'unmatched_page_scrape_queue'

    def process_name(self, job_type):
        return 'run_unmatched_page_scrape'

    def worker_run(self, **kwargs):
        run_class = UnmatchedRepoPage

        single_id = kwargs.get("id", None)
        limit = kwargs.get("limit", None)

        if limit is None:
            limit = float("inf")

        if single_id:
            page = run_class.query.filter(run_class.id == single_id).first()
            page.scrape()
            db.session.merge(page)
            safe_commit(db) or logger.info("COMMIT fail")
        else:
            index = 0
            start_time = time()

            while index < limit:
                new_loop_start_time = time()

                queued_page = self.fetch_queued_page()

                if not queued_page:
                    logger.info('no queued pages ready. waiting...')
                    sleep(5)
                    continue

                try:
                    # free up the connection while doing net IO
                    orm.make_transient(queued_page)
                    db.session.close()
                    db.engine.dispose()

                    queued_page.scrape()
                    db.session.merge(queued_page)
                except Exception as e:
                    queued_page.error += str(e)

                queue_update_text = '''
                    update {queue_table}
                    set finished = now(), started=null
                    where id = :id'''.format(queue_table=self.table_name(None))

                queue_update_command = text(queue_update_text).bindparams(id=queued_page.id)

                db.session.execute(queue_update_command)

                commit_start_time = time()
                safe_commit(db) or logger.info("COMMIT fail")
                logger.info("commit took {} seconds".format(elapsed(commit_start_time, 2)))

                index += 1
                self.print_update(new_loop_start_time, 1, limit, start_time, index)

    def fetch_queued_page(self):
        logger.info("looking for new jobs")

        job_time = time()
        page_id = db.engine.execute(self.queue_query.execution_options(autocommit=True)).scalar()

        if not page_id:
            return None

        logger.info("got page id {}, took {} seconds".format(page_id, elapsed(job_time, 4)))

        job_time = time()
        queue_page = db.session.query(UnmatchedRepoPage).options(orm.undefer('*')).get(page_id)

        logger.info("got UnmatchedRepoPage objects in {} seconds".format(elapsed(job_time, 4)))

        return queue_page


if __name__ == "__main__":
    if os.getenv('OADOI_LOG_SQL'):
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        db.session.configure()

    parser = argparse.ArgumentParser(description="run unmatched_page_scrape_queue")
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

    parsed_args = parser.parse_args()

    job_type = "normal"  # should be an object attribute
    my_queue = UnmatchedRepoPageScrape()
    my_queue.parsed_vars = vars(parsed_args)
    my_queue.run_right_thing(parsed_args, job_type)
