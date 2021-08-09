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

                fetch_result = self.fetch_queued_page()

                if not fetch_result['page']:
                    if fetch_result['sleep']:
                        logger.info('no queued pages ready. waiting...')
                        sleep(5)
                    continue

                queued_page = fetch_result['page']
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
        queue_page = None

        candidate_endpoint_id = db.session.execute(text('''
            select endpoint_id
            from endpoint_page_scrape_status
            where next_scrape_start < now()
            order by next_scrape_start
            limit 1 for update skip locked
        ''')).scalar()

        logger.info('got candidate endpoint id {}, took {} seconds'.format(candidate_endpoint_id, elapsed(job_time, 4)))

        if candidate_endpoint_id:
            selected_page_id = db.session.execute(text('''
                select id
                from unmatched_page_scrape_queue
                where
                    endpoint_id = :endpoint_id
                    and started is null
                    and (
                        finished is null
                        or finished < now() - interval '2 months'
                    )
                order by finished nulls first, rand
                limit 1
                for update skip locked
            ''').bindparams(endpoint_id=candidate_endpoint_id)).scalar()

            logger.info('got page id {}, took {} seconds'.format(selected_page_id, elapsed(job_time, 4)))

            if selected_page_id:
                db.session.execute(text('''
                    update endpoint_page_scrape_status
                    set next_scrape_start = now() + scrape_interval
                    where endpoint_id = :endpoint_id
                ''').bindparams(endpoint_id=candidate_endpoint_id))

                db.session.execute(text('''
                     update unmatched_page_scrape_queue
                     set started = now()
                     where id = :page_id
                 ''').bindparams(page_id=selected_page_id))
            else:
                db.session.execute(text('''
                    update endpoint_page_scrape_status
                    set next_scrape_start = now() + interval '15 minutes'
                    where endpoint_id = :endpoint_id
                ''').bindparams(endpoint_id=candidate_endpoint_id))

            db.session.commit()
            logger.info('updated queue for page id {}, took {} seconds'.format(selected_page_id, elapsed(job_time, 4)))

            if selected_page_id:
                queue_page = db.session.query(UnmatchedRepoPage).options(orm.undefer('*')).get(selected_page_id)
                logger.info("got UnmatchedRepoPage {}, took {} seconds".format(selected_page_id, elapsed(job_time, 4)))

        return {'page': queue_page, 'sleep': candidate_endpoint_id is None}


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
