from time import time
from time import sleep
import argparse
import logging

from sqlalchemy.dialects import postgresql
from sqlalchemy import orm
from sqlalchemy import text
from sqlalchemy import sql

from app import db
from app import ti_queues
from app import failed_queue
from util import elapsed
from util import chunks
from util import safe_commit



def update_fn(cls, method, obj_id_list, shortcut_data=None, index=1):

    # we are in a fork!  dispose of our engine.
    # will get a new one automatically
    # if is pooling, need to do .dispose() instead
    db.engine.dispose()

    start = time()

    # print u"obj_id_list: {}".format(obj_id_list)

    q = db.session.query(cls).options(orm.undefer('*')).filter(cls.id.in_(obj_id_list))

    obj_rows = q.all()

    num_obj_rows = len(obj_rows)
    print "{repr}.{method_name}() got {num_obj_rows} objects in {elapsed} seconds".format(
        repr=cls.__name__,
        method_name=method.__name__,
        num_obj_rows=num_obj_rows,
        elapsed=elapsed(start)
    )

    for count, obj in enumerate(obj_rows):
        start_time = time()

        if obj is None:
            return None

        method_to_run = getattr(obj, method.__name__)

        print u"\n***\n{count}: starting {repr}.{method_name}() method".format(
            count=count + (num_obj_rows*index),
            repr=obj,
            method_name=method.__name__
        )

        if shortcut_data:
            method_to_run(shortcut_data)
        else:
            method_to_run()

        print u"finished {repr}.{method_name}(). took {elapsed} seconds".format(
            repr=obj,
            method_name=method.__name__,
            elapsed=elapsed(start_time, 4)
        )

    print "committing\n\n"
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail"
    db.session.remove()  # close connection nicely
    return None  # important for if we use this on RQ



def enqueue_jobs(cls,
         method,
         ids_q_or_list,
         queue_number,
         use_rq=True,
         append=False,
         chunk_size=25,
         shortcut_fn=None
    ):
    """
    Takes sqlalchemy query with IDs, runs fn on those repos.
    """

    shortcut_data = None
    if use_rq:
        if shortcut_fn:
            raise ValueError("you can't use RQ with a shortcut_fn")

    else:
        if shortcut_fn:
            shortcut_data_start = time()
            print "Getting shortcut data..."
            shortcut_data = shortcut_fn()
            print "Got shortcut data in {} seconds".format(
                elapsed(shortcut_data_start)
            )

    chunk_size = int(chunk_size)


    start_time = time()
    new_loop_start_time = time()
    index = 0

    try:
        print "running this query: \n{}\n".format(
            ids_q_or_list.statement.compile(dialect=postgresql.dialect()))
        row_list = ids_q_or_list.all()

    except AttributeError:
        print "running this query: \n{}\n".format(ids_q_or_list)
        row_list = db.engine.execute(sql.text(ids_q_or_list)).fetchall()

    if row_list is None:
        print "no IDs, all done."
        return None

    print "finished query in {} seconds".format(elapsed(start_time))
    object_ids = [row[0] for row in row_list]

    # do this as late as possible so things can keep using queue
    if use_rq:
        if append:
            print "not clearing queue.  queue currently has {} jobs".format(ti_queues[queue_number].count)
        else:
            empty_queue(queue_number)


    num_items = len(object_ids)
    print "adding {} items to queue...".format(num_items)

    # iterate through chunks of IDs like [[id1, id2], [id3, id4], ...  ]
    object_ids_chunk = []

    for object_ids_chunk in chunks(object_ids, chunk_size):

        update_fn_args = [cls, method, object_ids_chunk]

        if use_rq:
            job = ti_queues[queue_number].enqueue_call(
                func=update_fn,
                args=update_fn_args,
                timeout=60 * 10,
                result_ttl=0  # number of seconds
            )
            job.meta["object_ids_chunk"] = object_ids_chunk
            job.save()
            # print u"saved job {}".format(job)
        else:
            update_fn_args.append(shortcut_data)
            update_fn(*update_fn_args, index=index)

        if True: # index % 10 == 0 and index != 0:
            num_jobs_remaining = num_items - (index * chunk_size)
            try:
                jobs_per_hour_this_chunk = chunk_size / float(elapsed(new_loop_start_time) / 3600)
                predicted_mins_to_finish = round(
                    (num_jobs_remaining / float(jobs_per_hour_this_chunk)) * 60,
                    1
                )
                print "\n\nWe're doing {} jobs per hour. At this rate, done in {}min".format(
                    int(jobs_per_hour_this_chunk),
                    predicted_mins_to_finish
                )
                print "(finished chunk {} of {} chunks in {} seconds total, {} seconds this loop)\n".format(
                    index,
                    num_items/chunk_size,
                    elapsed(start_time),
                    elapsed(new_loop_start_time)
                )
            except ZeroDivisionError:
                # print u"not printing status because divide by zero"
                print ".",


            new_loop_start_time = time()
        index += 1
    print "last chunk of ids: {}".format(list(object_ids_chunk))

    db.session.remove()  # close connection nicely
    return True






class UpdateRegistry():
    def __init__(self):
        self.updates = {}

    def register(self, update):
        self.updates[update.name] = update

    def get(self, update_name):
        return self.updates[update_name]

update_registry = UpdateRegistry()


class UpdateDbQueue():
    def __init__(self, **kwargs):
        self.job = kwargs["job"]
        self.method = self.job
        self.cls = self.job.im_class
        self.chunk = kwargs.get("chunk", 10)
        self.shortcut_fn = kwargs.get("shortcut_fn", None)
        self.name = "{}.{}".format(self.cls.__name__, self.method.__name__)
        self.queue_table = kwargs.get("queue_table", None)
        self.where = kwargs.get("where", None)
        self.queue_name = kwargs.get("queue_name", None)


    def run(self, **kwargs):
        id = kwargs.get("id", None)
        limit = kwargs.get("limit", 0)
        chunk = kwargs.get("chunk", self.chunk)

        after = kwargs.get("after", None)

        if not limit:
            limit = 1000

        ## based on http://dba.stackexchange.com/a/69497
        text_query_pattern = """WITH selected AS (
               SELECT *
               FROM   {table}
               WHERE  (queue is null or queue != '{queue_name}')
                      and {where}
               LIMIT  {chunk}
               FOR    UPDATE SKIP LOCKED
               )
            UPDATE {table} records_to_update
            SET    queue='{queue_name}'
            FROM   selected
            WHERE selected.id = records_to_update.id
            RETURNING records_to_update.id;"""

        text_query = text_query_pattern.format(
            table=self.queue_table,
            where=self.where,
            chunk=chunk,
            queue_name=self.queue_name)

        index = 0

        start_time = time()
        while (index * chunk) <= limit:
            new_loop_start_time = time()
            row_list = db.engine.execute(text_query).fetchall()
            if row_list is None:
                print "no more IDs, all done."
                return None
            print "finished query in {} seconds".format(elapsed(start_time))
            object_ids = [row[0] for row in row_list]

            update_fn_args = [self.cls, self.method, object_ids]
            # handle shortcut data here, when we want to

            update_fn(*update_fn_args, index=index)
            index += 1

            if True: # index % 10 == 0 and index != 0:
                num_items = limit  #let's say have to do the full limit
                num_jobs_remaining = num_items - (index * chunk)
                try:
                    jobs_per_hour_this_chunk = chunk / float(elapsed(new_loop_start_time) / 3600)
                    predicted_mins_to_finish = round(
                        (num_jobs_remaining / float(jobs_per_hour_this_chunk)) * 60,
                        1
                    )
                    print "\n\nWe're doing {} jobs per hour. At this rate, if we had to do everything up to limit, done in {}min".format(
                        int(jobs_per_hour_this_chunk),
                        predicted_mins_to_finish
                    )
                    print "(finished chunk {} of {} chunks in {} seconds total, {} seconds this loop)\n".format(
                        index,
                        num_items/chunk,
                        elapsed(start_time),
                        elapsed(new_loop_start_time)
                    )
                except ZeroDivisionError:
                    # print u"not printing status because divide by zero"
                    print ".",


class Update():
    def __init__(self, **kwargs):
        self.queue_id = kwargs.get("queue_id", None)
        self.query = kwargs["query"]
        self.job = kwargs["job"]
        self.method = self.job
        self.cls = self.job.im_class
        self.chunk = kwargs.get("chunk", 10)
        self.shortcut_fn = kwargs.get("shortcut_fn", None)
        self.name = "{}.{}".format(self.cls.__name__, self.method.__name__)


    def run(self, **kwargs):
        rq = kwargs.get("rq", False)
        id = kwargs.get("id", None)
        limit = kwargs.get("limit", 0)
        chunk = kwargs.get("chunk", self.chunk)
        after = kwargs.get("after", None)
        append = kwargs.get("append", False)

        if not limit:
            limit = 1000

        if rq:
            if self.queue_id is None:
                raise ValueError("you need a queue number to use RQ")

        query = self.query
        try:
            # do some query manipulation, unless it is a list of IDs
            # if num_jobs < 1000:
            #     query = query.order_by(self.cls.id)
            # else:
            #     print u"not using ORDER BY in query because too many jobs, would be too slow"

            if after:
                query = query.filter(self.cls.id > after)

            if id:
                # don't run the query, just get the id that was requested
                query = db.session.query(self.cls.id).filter(self.cls.id == id)
            else:
                query = query.limit(limit)
        except AttributeError:
            print u"appending limit to query string"
            query += u" limit {}".format(limit)

        enqueue_jobs(
            self.cls,
            self.method.__name__,
            query,
            self.queue_id,
            rq,
            append,
            chunk,
            self.shortcut_fn
        )




class UpdateStatus():
    seconds_between_chunks = 15

    def __init__(self, num_jobs, queue_number):
        self.num_jobs_total = num_jobs
        self.queue_number = queue_number
        self.start_time = time()

        self.last_chunk_start_time = time()
        self.last_chunk_num_jobs_completed = 0
        self.number_of_prints = 0



    def print_status_loop(self):
        num_jobs_remaining = self.print_status()
        while num_jobs_remaining > 0:
            num_jobs_remaining = self.print_status()


    def print_status(self):
        sleep(1)  # at top to make sure there's time for the jobs to be saved in redis.

        num_jobs_remaining = ti_queues[self.queue_number].count
        num_jobs_done = self.num_jobs_total - num_jobs_remaining


        print "finished {done} jobs in {elapsed} min. {left} left.".format(
            done=num_jobs_done,
            elapsed=round(elapsed(self.start_time) / 60, 1),
            left=num_jobs_remaining
        )
        self.number_of_prints += 1


        if self.number_of_prints % self.seconds_between_chunks == self.seconds_between_chunks - 1:

            num_jobs_finished_this_chunk = num_jobs_done - self.last_chunk_num_jobs_completed
            if not num_jobs_finished_this_chunk:
                print "No jobs finished this chunk... :/"

            else:
                chunk_elapsed = elapsed(self.last_chunk_start_time)

                jobs_per_hour_this_chunk = num_jobs_finished_this_chunk / float(chunk_elapsed / 3600)
                predicted_mins_to_finish = round(
                    (num_jobs_remaining / float(jobs_per_hour_this_chunk)) * 60,
                    1
                )
                print "We're doing {} jobs per hour. At this rate, done in {}min\n".format(
                    int(jobs_per_hour_this_chunk),
                    predicted_mins_to_finish
                )

                self.last_chunk_start_time = time()
                self.last_chunk_num_jobs_completed = num_jobs_done

        return num_jobs_remaining




def queue_status(queue_number_str):
    queue_number = int(queue_number_str)
    num_jobs_to_start = ti_queues[queue_number].count
    update = UpdateStatus(num_jobs_to_start, queue_number)
    update.print_status_loop()


def empty_queue(queue_number_str):
    queue_number = int(queue_number_str)
    num_jobs = ti_queues[queue_number].count
    ti_queues[queue_number].empty()

    print "emptied {} jobs on queue #{}....".format(
        num_jobs,
        queue_number
    )

    print "failed queue has {} items, also emptying it".format(failed_queue.count)
    failed_queue.empty()


def main(fn, optional_args=None):
    start = time()

    # call function by its name in this module, with all args :)
    # http://stackoverflow.com/a/4605/596939
    if optional_args:
        globals()[fn](*optional_args)
    else:
        globals()[fn]()

    print "total time to run: {} seconds".format(elapsed(start))


if __name__ == "__main__":

    # get args from the command line:
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('function', type=str, help="what function you want to run")
    parser.add_argument('optional_args', nargs='*', help="positional args for the function")

    args = vars(parser.parse_args())

    function = args["function"]
    optional_args = args["optional_args"]

    print u"running main.py {function} with these args:{optional_args}\n".format(
        function=function, optional_args=optional_args)

    global logger
    logger = logging.getLogger("ti.jobs.{function}".format(
        function=function))

    main(function, optional_args)

    db.session.remove()


