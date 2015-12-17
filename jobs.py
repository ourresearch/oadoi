from time import time
from time import sleep

from sqlalchemy.dialects import postgresql
from sqlalchemy import orm

from app import db
from app import ti_queues
from util import elapsed
from util import chunks


def person_load_options():
    from models.person import Person
    from models.contribution import Contribution
    from models.package import Package
    my_options = orm.subqueryload_all(
            Person.contributions, 
            Contribution.package, 
            Package.contributions 
            # Contribution.person,
            # Person.contributions
        )
    return my_options

def update_fn(cls, method_name, obj_id_list, shortcut_data=None):

    # we are in a fork!  dispose of our engine.
    # will get a new one automatically
    db.engine.dispose()

    start = time()

    q = db.session.query(cls).filter(cls.id.in_(obj_id_list))
    if cls.__name__ == "Person":
        q = q.options(person_load_options())


    obj_rows = q.all()
    num_obj_rows = len(obj_rows)
    print "{repr}.{method_name}() got {num_obj_rows} objects in {elapsed}sec".format(
        repr=cls.__name__,
        method_name=method_name,
        num_obj_rows=num_obj_rows,
        elapsed=elapsed(start)
    )

    for obj in obj_rows:
        start_time = time()

        if obj is None:
            return None

        method_to_run = getattr(obj, method_name)

        print u"\nstarting {repr}.{method_name}() method".format(
           repr=obj,
           method_name=method_name
        )

        if shortcut_data:
            method_to_run(shortcut_data)
        else:
            method_to_run()

        print u"finished {repr}.{method_name}(). took {elapsed}sec".format(
            repr=obj,
            method_name=method_name,
            elapsed=elapsed(start_time, 4)
        )

    db.session.commit()
    db.session.remove()  # close connection nicely
    return None  # important for if we use this on RQ



def enqueue_jobs(cls,
         method,
         ids_q_or_list,
         queue_number,
         use_rq="rq",
         chunk_size=10,
         shortcut_fn=None
    ):
    """
    Takes sqlalchemy query with (login, repo_name) IDs, runs fn on those repos.
    """

    shortcut_data = None
    if use_rq == "rq":
        empty_queue(queue_number)
        if shortcut_fn:
            raise ValueError("you can't use RQ with a shortcut_fn")

    else:
        if shortcut_fn:
            shortcut_data_start = time()
            print "Getting shortcut data..."
            shortcut_data = shortcut_fn()
            print "Got shortcut data in {}sec".format(
                elapsed(shortcut_data_start)
            )

    chunk_size = int(chunk_size)


    start_time = time()
    new_loop_start_time = time()
    index = 0

    print "running this query: \n{}\n".format(
        ids_q_or_list.statement.compile(dialect=postgresql.dialect())
    )
    row_list = ids_q_or_list.all()
    print "finished query in {}sec".format(elapsed(start_time))
    if row_list is None:
        print "no IDs, all done."
        return None

    object_ids = [row[0] for row in row_list]

    num_jobs = len(object_ids)
    print "adding {} jobs to queue...".format(num_jobs)

    # iterate through chunks of IDs like [[id1, id2], [id3, id4], ...  ]
    object_ids_chunk = []


    for object_ids_chunk in chunks(object_ids, chunk_size):

        update_fn_args = [cls, method, object_ids_chunk]

        if use_rq == "rq":
            job = ti_queues[queue_number].enqueue_call(
                func=update_fn,
                args=update_fn_args,
                timeout=60 * 10,
                result_ttl=0  # number of seconds
            )
            job.meta["object_ids_chunk"] = object_ids_chunk
            job.save()
        else:
            update_fn_args.append(shortcut_data)
            update_fn(*update_fn_args)

        if index % 1000 == 0 and index != 0:
            print "added {} jobs to queue in {}sec total, {}sec this loop".format(
                index,
                elapsed(start_time),
                elapsed(new_loop_start_time)
            )
            
            new_loop_start_time = time()
        index += 1
    print "last object added to the queue was {}".format(list(object_ids_chunk))

    db.session.remove()  # close connection nicely
    return True


def queue_status(queue_number_str):
    queue_number = int(queue_number_str)
    num_jobs_to_start = ti_queues[queue_number].count
    update = UpdateStatus(num_jobs_to_start, queue_number)
    update.print_status_loop()



class UpdateRegistry():
    def __init__(self):
        self.updates = {}

    def register(self, update):
        self.updates[update.name] = update

    def get(self, update_name):
        return self.updates[update_name]

update_registry = UpdateRegistry()


class Update():
    def __init__(self, job, query, queue_id=None, chunk_size_default=10, shortcut_fn=None):

        self.queue_id = queue_id
        self.job = job
        self.method = job
        self.cls = job.im_class
        self.chunk_size_default = chunk_size_default
        self.shortcut_fn = shortcut_fn

        self.name = "{}.{}".format(self.cls.__name__, self.method.__name__)
        self.query = query.order_by(self.cls.id)

    def run(self, no_rq=False, obj_id=None, num_jobs=None, chunk_size=None):

        if num_jobs is None:
            num_jobs = 1000

        if no_rq == False:
            use_rq = "rq"
            if self.queue_id is None:
                raise ValueError("you need a queue number to use RQ")
        else:
            use_rq = "you should not use RQ, computer."


        if chunk_size is None:
            chunk_size = self.chunk_size_default

        if obj_id is None:
            query = self.query.limit(num_jobs)
        else:
            # don't run the query, just get the id that was requested
            query = db.session.query(self.cls.id).filter(self.cls.id == obj_id)

        enqueue_jobs(
            self.cls,
            self.method.__name__,
            query,
            self.queue_id,
            use_rq,
            chunk_size,
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






def empty_queue(queue_number_str):
    queue_number = int(queue_number_str)
    num_jobs = ti_queues[queue_number].count
    ti_queues[queue_number].empty()

    print "emptied {} jobs on queue #{}....".format(
        num_jobs,
        queue_number
    )




