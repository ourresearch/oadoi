import argparse
import logging
import random
from time import sleep
from time import time

from sqlalchemy import orm
from sqlalchemy import text

from app import db
from app import logger
from pdf_url import PdfUrl
from pub import Pub
from queue_main import DbQueue
from util import clean_doi, safe_commit
from util import elapsed
from util import run_sql


def extract_pub_pdf_urls(pubs):
    pdf_urls = [
        PdfUrl(url=url, publisher=pub.publisher)
        for pub in pubs for url in pub.pdf_urls_to_check()
    ]

    for url in pdf_urls:
        logger.info(u'got a pdf url: {}'.format(url))
        db.session.merge(url)

    start_time = time()
    commit_success = safe_commit(db)
    if not commit_success:
        logger.info(u"COMMIT fail")
    logger.info(u"commit took {} seconds".format(elapsed(start_time, 2)))


class DbQueuePdfUrlExtract(DbQueue):
    def table_name(self, job_type):
        return 'pub_pdf_url_extract_queue'

    def process_name(self, job_type):
        return 'run_pdf_url_extract'

    def worker_run(self, **kwargs):
        run_class = Pub

        single_obj_id = kwargs.get("id", None)
        chunk_size = kwargs.get("chunk", 100)
        limit = kwargs.get("limit", None)

        if limit is None:
            limit = float("inf")

        if single_obj_id:
            single_obj_id = clean_doi(single_obj_id)
            objects = [run_class.query.filter(run_class.id == single_obj_id).first()]
            extract_pub_pdf_urls(objects)
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

                object_ids = [obj.id for obj in objects]
                extract_pub_pdf_urls(objects)

                object_ids_str = u",".join([u"'{}'".format(oid.replace(u"'", u"''")) for oid in object_ids])
                object_ids_str = object_ids_str.replace(u"%", u"%%")  # sql escaping

                sql_command = u"update {queue_table} set finished=now(), started=null where id in ({ids})".format(
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
                            select id
                            from {queue_table}
                            where started is null
                            order by finished asc nulls first, started, rand
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
        q = db.session.query(Pub).options(orm.undefer('*')).filter(Pub.id.in_(object_ids))
        objects = q.all()
        logger.info(u"got pub objects in {} seconds".format(elapsed(job_time)))

        random.shuffle(objects)

        return objects


if __name__ == "__main__":
    #logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    #db.session.configure()

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
    parser.add_argument('--chunk', "-ch", nargs="?", default=1000, type=int, help="how many to take off db at once")

    parsed_args = parser.parse_args()

    job_type = "normal"  # should be an object attribute
    my_queue = DbQueuePdfUrlExtract()
    my_queue.parsed_vars = vars(parsed_args)
    my_queue.run_right_thing(parsed_args, job_type)
