import os
import redis
import optparse
from rq import Worker
from rq import Queue
from rq import Connection
from app import redis_rq_conn


if __name__ == '__main__':
    parser = optparse.OptionParser("usage: %prog [options]")
    parser.add_option('-q', '--queue', dest='queue', type="str", default="scopus",
                      help='scopus')
    (options, args) = parser.parse_args()

    with Connection(redis_rq_conn):
        queue_name = options.queue
        queues = []
        for queue_name in [options.queue, "default"]:
            queues.append(Queue(queue_name))
        worker = Worker(queues)
        worker.work()

