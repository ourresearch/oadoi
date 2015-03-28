import os
import redis
import optparse
from rq import Worker
from rq import Queue
from rq import Connection

redis_rq_conn = redis.from_url(
                    os.getenv("REDIS_URL", "redis://127.0.0.1:6379"), 
                    db=4)

if __name__ == '__main__':
    parser = optparse.OptionParser("usage: %prog [options]")
    parser.add_option('-q', '--queue', dest='queue', type="str",
                      help='scopus')
    (options, args) = parser.parse_args()

    with Connection(redis_rq_conn):
        queue_name = options.queue
        queues = [queue_name, "default"]
        worker = Worker(map(Queue, queues))
        worker.work()

