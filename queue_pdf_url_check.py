import argparse
import os
import random
import logging
from datetime import datetime
from multiprocessing import Pool, current_process
from time import sleep
from time import time

from sqlalchemy import orm
from sqlalchemy import text
from sqlalchemy.orm import make_transient

from app import db
from app import logger
from http_cache import http_get, get_session_id
from pdf_url import PdfUrl
from queue_main import DbQueue
from util import elapsed
from util import run_sql
from util import safe_commit
from webpage import is_a_pdf_page

import endpoint # magic
import pmh_record # more magic

def check_pdf_urls(pdf_urls):
    for url in pdf_urls:
        make_transient(url)

    # free up the connection while doing net IO
    safe_commit(db)
    db.engine.dispose()

    req_pool = get_request_pool()

    checked_pdf_urls = req_pool.map(get_pdf_url_status, pdf_urls, chunksize=1)
    req_pool.close()
    req_pool.join()

    row_dicts = [x.__dict__ for x in checked_pdf_urls]
    for row_dict in row_dicts:
        row_dict.pop('_sa_instance_state')

    db.session.bulk_update_mappings(PdfUrl, row_dicts)

    start_time = time()
    commit_success = safe_commit(db)
    if not commit_success:
        logger.info(u"COMMIT fail")
    logger.info(u"commit took {} seconds".format(elapsed(start_time, 2)))


def get_pdf_url_status(pdf_url):
    worker = current_process()
    logger.info(u'{} checking pdf url: {}'.format(worker, pdf_url))

    is_pdf = False
    http_status = None

    try:
        response = http_get(
            url=pdf_url.url, ask_slowly=True, stream=True,
            publisher=pdf_url.publisher, session_id=get_session_id(),
            verify=True
        )
    except Exception as e:
        logger.error(u"{} failed to get response: {}".format(worker, e.message))
    else:
        with response:
            try:
                is_pdf = is_a_pdf_page(response, pdf_url.publisher)
                http_status = response.status_code
            except Exception as e:
                logger.error(u"{} failed reading response: {}".format(worker, e.message))

    pdf_url.is_pdf = is_pdf
    pdf_url.http_status = http_status
    pdf_url.last_checked = datetime.utcnow()

    logger.info(u'{} updated pdf url: {}'.format(worker, pdf_url))

    return pdf_url


def get_request_pool():
    num_request_workers = int(os.getenv('PDF_REQUEST_PROCS_PER_WORKER', 10))
    return Pool(processes=num_request_workers, maxtasksperchild=10)


class DbQueuePdfUrlCheck(DbQueue):
    def table_name(self, job_type):
        return 'pdf_url_check_queue'

    def process_name(self, job_type):
        return 'run_pdf_url_check'

    def worker_run(self, **kwargs):
        run_class = PdfUrl

        single_url = kwargs.get("id", None)
        chunk_size = kwargs.get("chunk", 100)
        limit = kwargs.get("limit", None)

        if limit is None:
            limit = float("inf")

        if single_url:
            objects = [run_class.query.filter(run_class.url == single_url).first()]
            check_pdf_urls(objects)
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

                check_pdf_urls(objects)

                object_ids = [obj.url for obj in objects]
                object_ids_str = u",".join([u"'{}'".format(oid.replace(u"'", u"''")) for oid in object_ids])
                object_ids_str = object_ids_str.replace(u"%", u"%%")  # sql escaping

                sql_command = u"""
                    update {queue_table} q
                    set
                        finished = now(),
                        started = null,
                        retry_interval = least(
                            case when is_pdf then '2 hours' else 4 * coalesce(retry_interval, '2 hours') end,
                            '2 months'
                        ),
                        retry_at = now() + case when is_pdf then '2 weeks' else coalesce(retry_interval, '2 hours') end
                    from
                        pdf_url
                    where
                        pdf_url.url = q.url
                        and q.url in ({ids})
                    """.format(
                        queue_table=self.table_name(None), ids=object_ids_str
                    )
                run_sql(db, sql_command)

                index += 1
                num_updated += len(objects)
                self.print_update(new_loop_start_time, chunk_size, limit, start_time, index)

    def fetch_queue_chunk(self, chunk_size):
        logger.info(u"looking for new jobs")

        text_query_pattern = """
                        with update_chunk as (
                            select url
                            from {queue_table}
                            where started is null
                            order by retry_at nulls first, finished nulls first, started, rand
                            limit {chunk_size}
                            for update skip locked
                        )
                        update {queue_table} queue_rows_to_update
                        set started=now()
                        from update_chunk
                        where update_chunk.url = queue_rows_to_update.url
                        returning update_chunk.url;
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
        q = db.session.query(PdfUrl).options(orm.undefer('*')).filter(PdfUrl.url.in_(object_ids))
        objects = q.all()
        logger.info(u"got pdf_url objects in {} seconds".format(elapsed(job_time)))

        random.shuffle(objects)
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
    my_queue = DbQueuePdfUrlCheck()
    my_queue.parsed_vars = vars(parsed_args)
    my_queue.run_right_thing(parsed_args, job_type)
