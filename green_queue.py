import os
import argparse
from time import time
from time import sleep
from sqlalchemy import sql
from sqlalchemy import exc
from subprocess import call
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
from app import HEROKU_APP_NAME

from oa_pmh import GreenLocation

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
    table_name = "doi_queue"
    if job_type=="hybrid":
        table_name += "_with_hybrid"
    elif job_type=="dates":
        table_name += "_dates"
    return table_name

def process_name(job_type):
    process_name = "run" # formation name is from Procfile
    if job_type=="hybrid":
        process_name += "_with_hybrid"
    elif job_type=="dates":
        process_name += "_dates"
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


def update_fn(cls, method, obj_id_list, shortcut_data=None, index=1):

    # we are in a fork!  dispose of our engine.
    # will get a new one automatically
    # if is pooling, need to do .dispose() instead
    db.engine.dispose()

    start = time()

    # logger(u"obj_id_list: {}".format(obj_id_list))

    q = db.session.query(cls).options(orm.undefer('*')).filter(cls.id.in_(obj_id_list))
    obj_rows = q.all()
    num_obj_rows = len(obj_rows)

    # if the queue includes items that aren't in the table, build them
    # assume they can be built by calling cls(id=id)
    if num_obj_rows != len(obj_id_list):
        logger.info(u"not all objects are there, so creating")
        ids_of_got_objects = [obj.id for obj in obj_rows]
        for id in obj_id_list:
            if id not in ids_of_got_objects:
                new_obj = cls(id=id)
                db.session.add(new_obj)
        safe_commit(db)
        logger.info(u"done")

    q = db.session.query(cls).options(orm.undefer('*')).filter(cls.id.in_(obj_id_list))
    obj_rows = q.all()
    num_obj_rows = len(obj_rows)

    logger.info(u"{pid} {repr}.{method_name}() got {num_obj_rows} objects in {elapsed} seconds".format(
        pid=os.getpid(),
        repr=cls.__name__,
        method_name=method.__name__,
        num_obj_rows=num_obj_rows,
        elapsed=elapsed(start)
    ))

    for count, obj in enumerate(obj_rows):
        start_time = time()

        if obj is None:
            return None

        method_to_run = getattr(obj, method.__name__)

        logger.info(u"***")
        logger.info(u"#{count} starting {repr}.{method_name}() method".format(
            count=count + (num_obj_rows*index),
            repr=obj,
            method_name=method.__name__
        ))

        if shortcut_data:
            method_to_run(shortcut_data)
        else:
            method_to_run()

        logger.info(u"finished {repr}.{method_name}(). took {elapsed} seconds".format(
            repr=obj,
            method_name=method.__name__,
            elapsed=elapsed(start_time, 4)
        ))


    logger.info(u"committing\n\n")
    start_time = time()
    commit_success = safe_commit(db)
    if not commit_success:
        logger.info(u"COMMIT fail")
    logger.info(u"commit took {} seconds".format(elapsed(start_time, 2)))
    db.session.remove()  # close connection nicely
    return None  # important for if we use this on RQ



class GreenLocationQueue(object):
    def __init__(self, **kwargs):
        self.job = kwargs["job"]
        self.method = self.job
        self.cls = self.job.im_class
        self.chunk = kwargs.get("chunk", 10)
        self.name = "{}.{}".format(self.cls.__name__, self.method.__name__)
        self.action_table = kwargs.get("action_table", None)
        self.where = kwargs.get("where", None)
        self.queue_name = kwargs.get("queue_name", None)


    def run(self, **kwargs):
        single_obj_id = kwargs.get("id", None)
        limit = kwargs.get("limit", 0)
        chunk = kwargs.get("chunk", self.chunk)
        queue_table = "doi_queue"

        if single_obj_id:
            limit = 1
        else:
            if not limit:
                limit = 1000

            my_dyno_name = os.getenv("DYNO", "unknown")
            text_query_pattern = """WITH picked_from_queue AS (
                       SELECT *
                       FROM   {queue_table}
                       WHERE  started is null
                       ORDER BY rand
                   LIMIT  {chunk}
                   FOR UPDATE SKIP LOCKED
                   )
                UPDATE {queue_table} doi_queue_rows_to_update
                SET    started=now(), dyno='{my_dyno_name}'
                FROM   picked_from_queue
                WHERE picked_from_queue.id = doi_queue_rows_to_update.id
                RETURNING doi_queue_rows_to_update.id;"""
            text_query = text_query_pattern.format(
                chunk=chunk,
                my_dyno_name=my_dyno_name,
                queue_table=queue_table
            )
            logger.info(u"the queue query is:\n{}".format(text_query))

        index = 0

        start_time = time()
        while True:
            new_loop_start_time = time()
            if single_obj_id:
                object_ids = [single_obj_id]
            else:
                # logger.info(u"looking for new jobs")
                row_list = db.engine.execute(text(text_query).execution_options(autocommit=True)).fetchall()
                object_ids = [row[0] for row in row_list]
                # logger.info(u"finished get-new-ids query in {} seconds".format(elapsed(new_loop_start_time)))

            if not object_ids:
                # logger.info(u"sleeping for 5 seconds, then going again")
                sleep(5)
                continue

            update_fn_args = [self.cls, self.method, object_ids]
            update_fn(*update_fn_args, index=index, shortcut_data=None)

            object_ids_str = u",".join(["'{}'".format(id) for id in object_ids])
            run_sql(db, "update {queue_table} set finished=now() where id in ({ids})".format(
                queue_table=queue_table, ids=object_ids_str))

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

    update.run(**vars(parsed_args))

    logger.info(u"finished update in {} seconds".format(elapsed(start)))

    resp = None
    if job_type in ("normal", "hybrid"):
        my_location = GreenLocation.query.get(parsed_args.id)
        resp = my_location.__dict__
        pprint(resp)

    return resp


# python doi_queue.py --hybrid --filename=data/dois_juan_accuracy.csv --dynos=40 --soup

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--id', nargs="?", type=str, help="id of the one thing you want to update (case sensitive)")
    parser.add_argument('--doi', nargs="?", type=str, help="id of the one thing you want to update (case insensitive)")

    parser.add_argument('--filename', nargs="?", type=str, help="filename with dois, one per line")
    parser.add_argument('--addall', default=False, action='store_true', help="add everything")
    parser.add_argument('--where', nargs="?", type=str, default=None, help="""where string for addall (eg --where="response_jsonb->>'oa_status'='green'")""")

    parser.add_argument('--hybrid', default=False, action='store_true', help="if hybrid, else don't include")
    parser.add_argument('--dates', default=False, action='store_true', help="use date queue")
    parser.add_argument('--all', default=False, action='store_true', help="do everything")

    parser.add_argument('--view', nargs="?", type=str, default=None, help="view name to export from")

    parser.add_argument('--reset', default=False, action='store_true', help="do you want to just reset?")
    parser.add_argument('--run', default=False, action='store_true', help="to run the queue")
    parser.add_argument('--status', default=False, action='store_true', help="to logger.info(the status")
    parser.add_argument('--dynos', default=None, type=int, help="scale to this many dynos")
    parser.add_argument('--export', default=False, action='store_true', help="export the results")
    parser.add_argument('--logs', default=False, action='store_true', help="logger.info(out logs")
    parser.add_argument('--monitor', default=False, action='store_true', help="monitor till done, then turn off dynos")
    parser.add_argument('--soup', default=False, action='store_true', help="soup to nuts")
    parser.add_argument('--kick', default=False, action='store_true', help="put started but unfinished dois back to unstarted so they are retried")


    parsed_args = parser.parse_args()
    job_type = "normal"
    if parsed_args.hybrid:
        job_type = "hybrid"
    if parsed_args.dates:
        job_type = "dates"

    if parsed_args.soup:
        if num_dynos(job_type) > 0:
            scale_dyno(0, job_type)
        if parsed_args.dynos:
            scale_dyno(parsed_args.dynos, job_type)
        else:
            logger.info(u"no number of dynos specified, so setting 1")
            scale_dyno(1, job_type)
        monitor_till_done(job_type)
        scale_dyno(0, job_type)
    else:
        if parsed_args.dynos != None:  # to tell the difference from setting to 0
            scale_dyno(parsed_args.dynos, job_type)
            # if parsed_args.dynos > 0:
            #     print_logs(job_type)

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

