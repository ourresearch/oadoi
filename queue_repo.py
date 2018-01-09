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
        process_name = "run_repo" # formation name is from Procfile
        return process_name

    def maint(self, **kwargs):
        repos = Repository.query.filter(Repository.name==None, Repository.error==None).all()
        num_to_commit = 0
        for my_repo in repos:
            if not my_repo.name:
                my_repo.set_repo_info()
                num_to_commit += 1
                db.session.merge(my_repo)
                logger.info(u"my_repo: {}".format(my_repo))
            if num_to_commit >= 1:
                safe_commit(db)
                num_to_commit = 0
        safe_commit(db)

    def add_pmh_record(self, **kwargs):
        repo_id = kwargs.get("id", None)
        record_id = kwargs.get("recordid")
        my_repo = Repository.query.get(repo_id)
        print "my_repo", my_repo
        my_pmh_record = my_repo.get_pmh_record(record_id)
        print "my_pmh_record", my_pmh_record

        my_pmh_record.mint_pages()

        # for my_page in my_pmh_record.pages:
        #     print "my_page", my_page
        #     my_page.scrape()

        db.session.merge(my_pmh_record)
        # print my_pmh_record.pages

        safe_commit(db)



    def worker_run(self, **kwargs):
        single_obj_id = kwargs.get("id", None)
        chunk = kwargs.get("chunk")
        queue_table = "repository"
        run_method = kwargs.get("method")
        run_class = Repository

        limit = 1 # just do one repo at a time

        if not single_obj_id:
            text_query_pattern = """WITH picked_from_queue AS (
                       SELECT *
                       FROM   {queue_table}
                       WHERE
                       (most_recent_year_harvested is null or (most_recent_year_harvested < now() - interval '1 day'))
                       and (last_harvest_started is null or
                            last_harvest_started < now() - interval '1 hour' or
                            last_harvest_finished is not null or
                            last_harvest_finished < now() - interval '1 day')
                        and (error is null or error='' or error like '%try again')
                        and ready_to_run=true
                        and id in ('citeseerx.ist.psu.edu/oai2', 'europepmc.org/oai.cgi', 'export.arxiv.org/oai2', 'www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi')
                       ORDER BY random() -- not rand, because want it to be different every time
                   LIMIT  {chunk}
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
            print "run_method", run_method
            self.update_fn(run_class, run_method, objects, index=index)

            # finished is set in update_fn
            index += 1
            if single_obj_id:
                return
            else:
                self.print_update(new_loop_start_time, chunk, limit, start_time, index)


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

        if parsed_args.add:
            self.add_pmh_record(**vars(parsed_args))
        elif parsed_args.maint:
            self.maint(**vars(parsed_args))
        else:
            if parsed_args.id or parsed_args.run:
                self.run(parsed_args, job_type)




# python queue_repo.py --hybrid --filename=data/dois_juan_accuracy.csv --dynos=40 --soup

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--id', nargs="?", type=str, help="id of the one thing you want to update (case sensitive)")
    parser.add_argument('--recordid', nargs="?", type=str, help="id of the record you want to update (case sensitive)")
    parser.add_argument('--method', nargs="?", type=str, default="harvest", help="method name to run")

    parser.add_argument('--run', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--status', default=False, action='store_true', help="to logger.info(the status")
    parser.add_argument('--dynos', default=None, type=int, help="scale to this many dynos")
    parser.add_argument('--logs', default=False, action='store_true', help="logger.info(out logs")
    parser.add_argument('--monitor', default=False, action='store_true', help="monitor till done, then turn off dynos")
    parser.add_argument('--kick', default=False, action='store_true', help="put started but unfinished dois back to unstarted so they are retried")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many jobs to do")
    parser.add_argument('--chunk', "-ch", nargs="?", default=1, type=int, help="how many to take off db at once")
    parser.add_argument('--maint', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--tilltoday', default=False, action='store_true', help="run all the years till today")

    parser.add_argument('--add', default=False, action='store_true', help="how many to take off db at once")

    parsed_args = parser.parse_args()

    job_type = "normal"  #should be an object attribute
    my_queue = DbQueueRepo()
    my_queue.run_right_thing(parsed_args, job_type)
    print "finished"
