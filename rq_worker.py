import optparse
import os
import sys
import logging
from rq import Worker
from rq import Queue
from rq import Connection
from rq.job import JobStatus
from app import redis_rq_conn
from app import ti_queues
import argparse




def failed_job_handler(job, exc_type, exc_value, traceback):

    print "RQ job failed! {}. here's more: {} {} {}".format(
        job.meta, exc_type, exc_value, traceback
    )
    return True  # job failed, drop to next level error handling

def start_worker(queue_name):
    print "starting worker '{}'...".format(queue_name)

    with Connection(redis_rq_conn):
        worker = Worker(Queue(queue_name), exc_handler=failed_job_handler)
        worker.work()



if __name__ == '__main__':

    # get args from the command line:
    parser = argparse.ArgumentParser(description="Run RQ workers on a given queue.")
    parser.add_argument('queue_number', type=int, help="the queue number you want this worker to listen on.")

    args = vars(parser.parse_args())

    queue_name = "ti-queue-{}".format(args["queue_number"])

    print u"Starting an RQ worker, listening on '{queue_name}'\n".format(
        queue_name=queue_name
    )
    start_worker(queue_name)

