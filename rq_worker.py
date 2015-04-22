import optparse
import os
import sys
import logging
from rq import Worker
from rq import Queue
from rq import Connection
from rq.job import JobStatus
from app import redis_rq_conn


# set up logging
# see http://wiki.pylonshq.com/display/pylonscookbook/Alternative+logging+configuration
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='[%(process)3d] %(levelname)8s %(threadName)30s %(name)s - %(message)s'
)
logger = logging.getLogger("rq_worker")


# from http://stackoverflow.com/questions/12774085/dealing-with-exception-handling-and-re-queueing-in-rq-on-heroku/16326962#16326962
def retry_handler(job, exc_type, exc_value, traceback):
    # Returning True moves the job to the failed queue (or continue to
    # the next handler)

    job.meta.setdefault('failures', 1)
    job.meta['failures'] += 1
    # if job.meta['failures'] > 3 or isinstance(exc_type, (LookupError, CorruptImageError)):
    if job.meta['failures'] > 3:
        logger.info("job failed > 3 times, so don't retry")
        job.save()
        return True

    logger.info("job failed, now retry it")
    job.status = JobStatus.QUEUED
    for queue_ in Queue.all():
        if queue_.name == job.origin:
            queue_.enqueue_job(job)
            break
    else:
        return True  # Queue has disappeared, fail job

    return False  # Job is handled. Stop the handler chain.



def start_worker(queue_name, worker_name=None):
    logger.info("starting worker {worker_name} for queue '{queue_name}'".format(
            queue_name=queue_name, 
            worker_name=worker_name))

    with Connection(redis_rq_conn):
        # first, clean up any old workers with same name
        if worker_name:
            for worker in Worker.all():
                if worker_name == worker.name:
                    # like http://stackoverflow.com/a/15184174/596939
                    worker.register_death()

        queues = []
        for queue_name in [queue_name, "default"]:
            queues.append(Queue(queue_name))
        worker = Worker(queues, name=worker_name, exc_handler=retry_handler)
        worker.work()


if __name__ == '__main__':
    parser = optparse.OptionParser("usage: %prog [options]")
    parser.add_option('-q', '--queue', dest='queue', type="str", default=queue_name,
                      help=queue_name)
    parser.add_option('-n', '--name', dest='name', type="str", default=None)
    (options, args) = parser.parse_args()
    start_worker(options.queue, options.name)



