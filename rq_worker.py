import optparse
from rq import Worker
from rq import Queue
from rq import Connection
from app import redis_rq_conn


def start_worker(queue_name):
    print "starting worker for queue '{queue}'".format(queue=queue_name)
    parser = optparse.OptionParser("usage: %prog [options]")
    parser.add_option('-q', '--queue', dest='queue', type="str", default=queue_name,
                      help=queue_name)
    (options, args) = parser.parse_args()

    with Connection(redis_rq_conn):
        queue_name = options.queue
        queues = []
        for queue_name in [options.queue, "default"]:
            queues.append(Queue(queue_name))
        worker = Worker(queues)
        worker.work()

