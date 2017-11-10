import os
import argparse
from time import time
from time import sleep
from sqlalchemy import sql
from sqlalchemy import exc
from subprocess import call
from sqlalchemy import text
from sqlalchemy import orm
import heroku3
from pprint import pprint
import datetime


from app import db
from app import logger

from queue_main import DbQueue
from util import elapsed
from util import safe_commit

from repository import Repository

class DbQueueRepo(DbQueue):
    def table_name(self, job_type):
        table_name = "repository"
        return table_name

    def process_name(self, job_type):
        process_name = "run_green" # formation name is from Procfile
        return process_name

    def worker_run(self, **kwargs):
        single_obj_id = kwargs.get("id", None)
        chunk = kwargs.get("chunk", 10)
        queue_table = "repository"
        run_class = Repository
        run_method = "harvest"

        limit = 1 # just do one repo at a time

        text_query_pattern = """WITH picked_from_queue AS (
                   SELECT *
                   FROM   {queue_table}
                   WHERE  last_harvest_started is null or last_harvest_finished is not null
                   ORDER BY random() -- not rand, because want it to be different every time
               LIMIT  1
               FOR UPDATE SKIP LOCKED
               )
            UPDATE {queue_table} queue_rows_to_update
            SET    last_harvest_started=now() at time zone 'utc', last_harvest_finished=null
            FROM   picked_from_queue
            WHERE picked_from_queue.id = queue_rows_to_update.id
            RETURNING picked_from_queue.*;"""
        text_query = text_query_pattern.format(
            chunk=chunk,
            queue_table=queue_table
        )
        logger.info(u"the queue query is:\n{}".format(text_query))

        index = 0
        start_time = time()
        while True:
            new_loop_start_time = time()
            if single_obj_id:
                objects = [run_class.query.filter(run_class.id == single_obj_id).first()]
            else:
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
                self.print_update(new_loop_start_time, chunk, limit, start_time, index)




# python queue_repo.py --hybrid --filename=data/dois_juan_accuracy.csv --dynos=40 --soup

if __name__ == "__main__":
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
    parser.add_argument('--chunk', "-ch", nargs="?", default=10, type=int, help="how many to take off db at once")

    parsed_args = parser.parse_args()

    job_type = "normal"  #should be an object attribute
    my_queue = DbQueueRepo()
    my_queue.run_right_thing(parsed_args, job_type)
    print "finished"
