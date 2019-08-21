import argparse
import logging
import os
import redis
import pickle
import datetime
from multiprocessing import Pool, current_process
from time import sleep
from time import time
from urlparse import urlparse
from redis import WatchError

from sqlalchemy import orm, sql, text
from sqlalchemy.orm import make_transient

from app import db
from app import logger
from oa_page import oa_publisher_equivalent
from page import PageNew
from queue_main import DbQueue
from util import elapsed
from util import safe_commit

from pub import Pub # foul magic
import endpoint # magic
import pmh_record # more magic


def scrape_pages(pages):
    for page in pages:
        make_transient(page)

    # free up the connection while doing net IO
    db.session.close()
    db.engine.dispose()

    pool = get_worker_pool()
    scraped_pages = [p for p in pool.map(scrape_page, pages, chunksize=1) if p]
    logger.info(u'finished scraping all pages')
    pool.close()
    pool.join()

    logger.info(u'preparing update records')
    row_dicts = [x.__dict__ for x in scraped_pages]
    for row_dict in row_dicts:
        row_dict.pop('_sa_instance_state')

    logger.info(u'saving update records')
    db.session.bulk_update_mappings(PageNew, row_dicts)

    scraped_page_ids = [p.id for p in scraped_pages]
    return scraped_page_ids


def get_worker_pool():
    num_request_workers = int(os.getenv('GREEN_SCRAPE_PROCS_PER_WORKER', 10))
    return Pool(processes=num_request_workers, maxtasksperchild=10)


def scrape_page(page):
    worker = current_process().name
    domain = urlparse(page.url).netloc
    logger.info(u'{} started scraping page at {}: {}'.format(worker, domain, page))
    if begin_rate_limit_domain(domain):
        page.scrape()
        end_rate_limit_domain(domain)
        logger.info(u'{} finished scraping page: {}'.format(worker, page))
        return page
    else:
        logger.info(u'{} not ready to scrape {}'.format(worker, domain))
        return None


def unpickle(v):
    return pickle.loads(v) if v else None


def redis_key(domain):
    return u'green-scrape:{}'.format(domain)


def begin_rate_limit_domain(domain, interval_seconds=10):
    r = redis.from_url(os.environ.get("REDIS_URL"))

    with r.pipeline() as pipe:
        try:
            pipe.watch(redis_key(domain))

            scrape_started = unpickle(r.hget(redis_key(domain), 'started'))
            scrape_finished = unpickle(r.hget(redis_key(domain), 'finished'))

            if scrape_started or (
                scrape_finished and
                scrape_finished >= datetime.datetime.utcnow() - datetime.timedelta(seconds=interval_seconds) and
                scrape_started >= datetime.datetime.utcnow() - datetime.timedelta(hours=1)
            ):
                return False

            pipe.multi()
            pipe.hset(redis_key(domain), 'started', pickle.dumps(datetime.datetime.utcnow()))
            pipe.hset(redis_key(domain), 'finished', pickle.dumps(None))
            pipe.execute()
            return True
        except WatchError:
            return False


def end_rate_limit_domain(domain):
    r = redis.from_url(os.environ.get("REDIS_URL"))

    r.hset(redis_key(domain), 'started', pickle.dumps(None))
    r.hset(redis_key(domain), 'finished', pickle.dumps(datetime.datetime.utcnow()))


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
        scrape_publisher = kwargs.get("scrape_publisher", False)

        if limit is None:
            limit = float("inf")

        if single_id:
            page = run_class.query.filter(run_class.id == single_id).first()
            page.scrape()
            db.session.merge(page)
            safe_commit(db) or logger.info(u"COMMIT fail")
        else:
            index = 0
            num_updated = 0
            start_time = time()

            while num_updated < limit:
                new_loop_start_time = time()

                objects = self.fetch_queue_chunk(chunk_size, scrape_publisher)

                if not objects:
                    sleep(5)
                    continue

                scraped_ids = scrape_pages(objects)
                unscraped_ids = [obj.id for obj in objects if obj.id not in scraped_ids]

                logger.info(u'scraped {} pages and returned {} to the queue'.format(
                    len(scraped_ids), len(unscraped_ids)
                ))

                scraped_batch_text = u'''
                    update {queue_table}
                    set finished = now(), started=null
                    where id = any(:ids)'''.format(queue_table=self.table_name(None))

                unscraped_batch_text = u'''
                     update {queue_table}
                     set started=null
                     where id = any(:ids)'''.format(queue_table=self.table_name(None))

                scraped_batch_command = text(scraped_batch_text).bindparams(
                    ids=scraped_ids)

                unscraped_batch_command = text(unscraped_batch_text).bindparams(
                    ids=unscraped_ids)

                db.session.execute(scraped_batch_command)
                db.session.execute(unscraped_batch_command)

                commit_start_time = time()
                safe_commit(db) or logger.info(u"COMMIT fail")
                logger.info(u"commit took {} seconds".format(elapsed(commit_start_time, 2)))

                index += 1
                num_updated += len(objects)
                self.print_update(new_loop_start_time, len(scraped_ids), limit, start_time, index)

    def fetch_queue_chunk(self, chunk_size, scrape_publisher):
        logger.info(u"looking for new jobs")

        if scrape_publisher:
            pmh_value_filter = "and pmh_id = '{}'".format(oa_publisher_equivalent)
        else:
            pmh_value_filter = "and pmh_id is distinct from '{}'".format(oa_publisher_equivalent)

        text_query_pattern = """
                        with update_chunk as (
                            select id
                            from
                                {queue_table} q
                                join page_new p using (id)
                            where
                                q.started is null
                                {pmh_value_filter}
                            order by q.finished asc nulls first, q.started, q.rand
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
            queue_table=self.table_name(None),
            pmh_value_filter=pmh_value_filter
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

    parser.add_argument('--scrape-publisher', default=False, action='store_true', help="scrape publisher-equivalent pages")

    parsed_args = parser.parse_args()

    job_type = "normal"  # should be an object attribute
    my_queue = DbQueueGreenOAScrape()
    my_queue.parsed_vars = vars(parsed_args)
    my_queue.run_right_thing(parsed_args, job_type)
