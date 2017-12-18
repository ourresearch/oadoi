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

from util import elapsed
from util import run_sql
from util import get_sql_answer
from util import get_sql_answers
from util import clean_doi
from util import safe_commit
from app import HEROKU_APP_NAME

from page import PageNew
from pub import Pub  #important so we can get the doi object, and therefore its base stuff

def monitor_till_done(job_type):
    logger.info(u"collecting data. will have some stats soon...")
    logger.info(u"\n\n")

    num_total = number_total_on_queue(job_type)
    print "num_total", num_total
    num_unfinished = number_unfinished(job_type)
    print "num_unfinished", num_unfinished

    loop_thresholds = {"short": 30, "long": 10*60, "medium": 60}
    loop_unfinished = {"short": num_unfinished, "long": num_unfinished}
    loop_start_time = {"short": time(), "long": time()}

    # print_idle_dynos(job_type)

    while all(loop_unfinished.values()):
        for loop in ["short", "long"]:
            if elapsed(loop_start_time[loop]) > loop_thresholds[loop]:
                if loop in ["short", "long"]:
                    num_unfinished_now = number_unfinished(job_type)
                    num_finished_this_loop = loop_unfinished[loop] - num_unfinished_now
                    loop_unfinished[loop] = num_unfinished_now
                    if loop=="long":
                        logger.info(u"\n****"),
                    logger.info(u"   {} finished in the last {} seconds, {} of {} are now finished ({}%).  ".format(
                        num_finished_this_loop, loop_thresholds[loop],
                        num_total - num_unfinished_now,
                        num_total,
                        int(100*float(num_total - num_unfinished_now)/num_total)
                    )),  # comma so the next part will stay on the same line
                    if num_finished_this_loop:
                        minutes_left = float(num_unfinished_now) / num_finished_this_loop * loop_thresholds[loop] / 60
                        logger.info(u"{} estimate: done in {} mins, which is {} hours".format(
                            loop, round(minutes_left, 1), round(minutes_left/60, 1)))
                    else:
                        print
                    loop_start_time[loop] = time()
                    # print_idle_dynos(job_type)
        print".",
        sleep(3)
    logger.info(u"everything is done.  turning off all the dynos")
    scale_dyno(0, job_type)


def number_total_on_queue(job_type):
    num = get_sql_answer(db, "select count(*) from {}".format(table_name(job_type)))
    return num

def number_waiting_on_queue(job_type):
    num = get_sql_answer(db, "select count(*) from {} where started is null".format(table_name(job_type)))
    return num

def number_unfinished(job_type):
    num = get_sql_answer(db, "select count(*) from {} where finished is null".format(table_name(job_type)))
    return num

def print_status(job_type):
    num_dois = number_total_on_queue(job_type)
    num_waiting = number_waiting_on_queue(job_type)
    if num_dois:
        logger.info(u"There are {} dois in the queue, of which {} ({}%) are waiting to run".format(
            num_dois, num_waiting, int(100*float(num_waiting)/num_dois)))

def kick(job_type):
    q = u"""update {table_name} set started=null, finished=null
          where finished is null""".format(
          table_name=table_name(job_type))
    run_sql(db, q)
    print_status(job_type)

def reset_enqueued(job_type):
    q = u"update {} set started=null, finished=null".format(table_name(job_type))
    run_sql(db, q)

def truncate(job_type):
    q = "truncate table {}".format(table_name(job_type))
    run_sql(db, q)

def table_name(job_type):
    table_name = "page_new"
    return table_name

def process_name(job_type):
    process_name = "run_green" # formation name is from Procfile
    return process_name

def num_dynos(job_type):
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    num_dynos = 0
    try:
        dynos = heroku_conn.apps()[HEROKU_APP_NAME].dynos()[process_name(job_type)]
        num_dynos = len(dynos)
    except (KeyError, TypeError) as e:
        pass
    return num_dynos

def print_idle_dynos(job_type):
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    app = heroku_conn.apps()[HEROKU_APP_NAME]
    running_dynos = []
    try:
        running_dynos = [dyno for dyno in app.dynos() if dyno.name.startswith(process_name(job_type))]
    except (KeyError, TypeError) as e:
        pass

    dynos_still_working = get_sql_answers(db, "select dyno from {} where started is not null and finished is null".format(table_name(job_type)))
    dynos_still_working_names = [n for n in dynos_still_working]

    logger.info(u"dynos still running: {}".format([d.name for d in running_dynos if d.name in dynos_still_working_names]))
    # logger.info(u"dynos stopped:", [d.name for d in running_dynos if d.name not in dynos_still_working_names])
    # kill_list = [d.kill() for d in running_dynos if d.name not in dynos_still_working_names]

def scale_dyno(n, job_type):
    logger.info(u"starting with {} dynos".format(num_dynos(job_type)))
    logger.info(u"setting to {} dynos".format(n))
    heroku_conn = heroku3.from_key(os.getenv("HEROKU_API_KEY"))
    app = heroku_conn.apps()[HEROKU_APP_NAME]
    app.process_formation()[process_name(job_type)].scale(n)

    logger.info(u"sleeping for 2 seconds while it kicks in")
    sleep(2)
    logger.info(u"verifying: now at {} dynos".format(num_dynos(job_type)))



def print_logs(job_type):
    command = "heroku logs -t --dyno={}".format(process_name(job_type))
    call(command, shell=True)


def update_fn(cls, method_name, green_locations, index=1):

    # we are in a fork!  dispose of our engine.
    # will get a new one automatically
    # if is pooling, need to do .dispose() instead
    db.engine.dispose()

    start = time()
    num_obj_rows = len(green_locations)

    logger.info(u"{pid} {repr}.{method_name}() got {num_obj_rows} objects in {elapsed} seconds".format(
        pid=os.getpid(),
        repr=cls.__name__,
        method_name=method_name,
        num_obj_rows=num_obj_rows,
        elapsed=elapsed(start)
    ))

    for count, obj in enumerate(green_locations):
        start_time = time()

        if obj is None:
            return None

        method_to_run = getattr(obj, method_name)

        logger.info(u"***")
        logger.info(u"#{count} starting {repr}.{method_name}() method".format(
            count=count + (num_obj_rows*index),
            repr=obj,
            method_name=method_name
        ))

        method_to_run()

        logger.info(u"finished {repr}.{method_name}(). took {elapsed} seconds".format(
            repr=obj,
            method_name=method_name,
            elapsed=elapsed(start_time, 4)
        ))

        # for handling the queue
        obj.finished = datetime.datetime.utcnow().isoformat()


    logger.info(u"committing\n\n")
    start_time = time()
    commit_success = safe_commit(db)
    if not commit_success:
        logger.info(u"COMMIT fail")
    logger.info(u"commit took {} seconds".format(elapsed(start_time, 2)))
    db.session.remove()  # close connection nicely
    return None  # important for if we use this on RQ



def worker_run(**kwargs):
    single_obj_id = kwargs.get("id", None)
    limit = kwargs.get("limit", 0)
    chunk = kwargs.get("chunk", 10)
    queue_table = "page_new"
    run_class = PageNew
    run_method = "scrape"

    if single_obj_id:
        limit = 1
    else:
        if not limit:
            limit = 1000
        text_query_pattern = """WITH picked_from_queue AS (
                   SELECT *
                   FROM   {queue_table}
                   WHERE  started is null
                   ORDER BY rand
               LIMIT  {chunk}
               FOR UPDATE SKIP LOCKED
               )
            UPDATE {queue_table} doi_queue_rows_to_update
            SET    started=now()
            FROM   picked_from_queue
            WHERE picked_from_queue.id = doi_queue_rows_to_update.id
              and picked_from_queue.url = doi_queue_rows_to_update.url
              and picked_from_queue.doi = doi_queue_rows_to_update.doi
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
            green_locations = [PageNew.query.filter(PageNew.pmh_id == single_obj_id).first()]
        else:
            # logger.info(u"looking for new jobs")
            green_locations = PageNew.query.from_statement(text(text_query)).execution_options(autocommit=True).all()
            # logger.info(u"finished get-new-objects query in {} seconds".format(elapsed(new_loop_start_time)))

        if not green_locations:
            # logger.info(u"sleeping for 5 seconds, then going again")
            sleep(5)
            continue

        object_ids = [location.id for location in green_locations]
        update_fn(run_class, run_method, green_locations, index=index)

        # finished is set in update_fn

        index += 1

        if single_obj_id:
            return
        else:
            num_items = limit  #let's say have to do the full limit
            num_jobs_remaining = num_items - (index * chunk)
            try:
                jobs_per_hour_this_chunk = chunk / float(elapsed(new_loop_start_time) / 3600)
                predicted_mins_to_finish = round(
                    (num_jobs_remaining / float(jobs_per_hour_this_chunk)) * 60,
                    1
                )
                logger.info(u"\n\nWe're doing {} jobs per hour. At this rate, if we had to do everything up to limit, done in {}min".format(
                    int(jobs_per_hour_this_chunk),
                    predicted_mins_to_finish
                ))
                logger.info(u"\t{} seconds this loop, {} chunks in {} seconds, {} seconds/chunk average\n".format(
                    elapsed(new_loop_start_time),
                    index,
                    elapsed(start_time),
                    round(elapsed(start_time)/float(index), 1)
                ))
            except ZeroDivisionError:
                # logger.info(u"not printing status because divide by zero")
                logger.info(u"."),



def run(parsed_args, job_type):
    start = time()

    worker_run(**vars(parsed_args))

    logger.info(u"finished update in {} seconds".format(elapsed(start)))
    # resp = None
    # if job_type in ["normal"]:
    #     my_location = PageNew.query.get(parsed_args.id)
    #     resp = my_location.__dict__
    #     pprint(resp)

    print "done"
    return


# python doi_queue.py --hybrid --filename=data/dois_juan_accuracy.csv --dynos=40 --soup

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
    job_type = "normal"

    if parsed_args.dynos != None:  # to tell the difference from setting to 0
        scale_dyno(parsed_args.dynos, job_type)

    if parsed_args.reset:
        reset_enqueued(job_type)

    if parsed_args.status:
        print_status(job_type)

    if parsed_args.monitor:
        monitor_till_done(job_type)
        scale_dyno(0, job_type)

    if parsed_args.logs:
        print_logs(job_type)

    if parsed_args.kick:
        kick(job_type)

    if parsed_args.id or parsed_args.doi or parsed_args.run:
        run(parsed_args, job_type)

    print "finished"
