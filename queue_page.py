import os
import argparse
from time import time
from time import sleep
from sqlalchemy import sql
from sqlalchemy import exc
from subprocess import call
from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy import or_
import heroku3
from pprint import pprint
import datetime
from random import random

from app import db
from app import logger

from queue_main import DbQueue
from util import elapsed
from util import safe_commit
from pub import Pub
from page import PageNew


class DbQueueRepo(DbQueue):

    def table_name(self, job_type):
        table_name = "page_new"
        return table_name

    def process_name(self, job_type):
        process_name = "run_page" # formation name is from Procfile
        return process_name


    def worker_run(self, **kwargs):
        single_obj_id = kwargs.get("id", None)
        chunk = kwargs.get("chunk")
        queue_table = "page_new"
        run_method = kwargs.get("method")
        run_class = PageNew

        if not single_obj_id:
            text_query_pattern = """WITH picked_from_queue AS (
                   SELECT *
                   FROM   {queue_table}
                   WHERE  started is null and num_pub_matches is null
                   -- and rand > {rand_thresh}
                   and repo_id not in ('quod.lib.umich.edu/cgi/o/oai/oai')
                   and repo_id='digitallibrary.amnh.org/oai/request' --remove
                   ORDER BY rand
               LIMIT  {chunk}
               FOR UPDATE SKIP LOCKED
               )
            UPDATE {queue_table} rows_to_update
            SET    started=now()
            FROM   picked_from_queue
            WHERE picked_from_queue.id = rows_to_update.id
            RETURNING picked_from_queue.*;"""
            logger.info(u"the queue text_query_pattern is:\n{}".format(text_query_pattern))

        index = 0
        start_time = time()
        while True:
            new_loop_start_time = time()
            if single_obj_id:
                objects = [run_class.query.filter(or_(run_class.id == single_obj_id,
                                                      run_class.url == single_obj_id,
                                                      run_class.pmh_id == single_obj_id)).first()]
            else:
                text_query = text_query_pattern.format(
                    chunk=chunk,
                    queue_table=queue_table,
                    rand_thresh=random()
                )
                # logger.info(u"looking for new jobs")
                objects = run_class.query.from_statement(text(text_query)).execution_options(autocommit=True).all()
                # logger.info(u"finished get-new-objects query in {} seconds".format(elapsed(new_loop_start_time)))

            if not objects:
                # logger.info(u"sleeping for 5 seconds, then going again")
                sleep(5)
                continue

            object_ids = [obj.id for obj in objects]
            self.update_fn(run_class, run_method, objects, index=index)

            # finished is set in update_fn
            index += 1
            if single_obj_id:
                return
            else:
                self.print_update(new_loop_start_time, chunk, chunk, start_time, index)


    def run_right_thing(self, parsed_args, job_type):
        if parsed_args.dynos != None:  # to tell the difference from setting to 0
            self.scale_dyno(parsed_args.dynos, job_type)

        if parsed_args.status:
            self.print_status(job_type)

        if parsed_args.monitor:
            self.monitor_till_done(job_type)
            self.scale_dyno(0, job_type)

        if parsed_args.logs:
            self.print_logs(job_type)

        if parsed_args.kick:
            self.kick(job_type)

        if parsed_args.id or parsed_args.run:
            self.run(parsed_args, job_type)




# python queue_repo.py --hybrid --filename=data/dois_juan_accuracy.csv --dynos=40 --soup

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--id', nargs="?", type=str, help="id of the one thing you want to update (case sensitive)")
    parser.add_argument('--method', nargs="?", type=str, default="scrape_if_matches_pub", help="method name to run")

    parser.add_argument('--run', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--status', default=False, action='store_true', help="to logger.info(the status")
    parser.add_argument('--dynos', default=None, type=int, help="scale to this many dynos")
    parser.add_argument('--logs', default=False, action='store_true', help="logger.info(out logs")
    parser.add_argument('--monitor', default=False, action='store_true', help="monitor till done, then turn off dynos")
    parser.add_argument('--kick', default=False, action='store_true', help="put started but unfinished dois back to unstarted so they are retried")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many jobs to do")
    parser.add_argument('--chunk', "-ch", nargs="?", default=3, type=int, help="how many to take off db at once")

    parsed_args = parser.parse_args()

    job_type = "normal"  #should be an object attribute
    my_queue = DbQueueRepo()
    my_queue.run_right_thing(parsed_args, job_type)
    print "finished"



