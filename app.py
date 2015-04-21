from flask import Flask
import redis
import os
from rq import Queue


app = Flask(__name__)
app.debug = True

my_redis = redis.from_url(
    os.getenv("REDIS_URL", "redis://127.0.0.1:6379"),
    db=10
)

redis_rq_conn = redis.from_url(
    os.getenv("REDIS_URL", "redis://127.0.0.1:6379"),
    db=14
)


scopus_queue = Queue("scopus", connection=redis_rq_conn)
refset_queue = Queue("refset", connection=redis_rq_conn)
