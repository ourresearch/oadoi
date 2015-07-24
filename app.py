import os

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from sqlalchemy import event
from sqlalchemy.pool import Pool

import redis
from rq import Queue

import os
import logging
import sys


# set up logging
# see http://wiki.pylonshq.com/display/pylonscookbook/Alternative+logging+configuration
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='[%(process)3d] %(levelname)8s %(threadName)30s %(name)s - %(message)s'
)
logger = logging.getLogger("software")

libraries_to_mum = [
    "requests.packages.urllib3",
    "stripe",
    "oauthlib",
    "boto",
    "newrelic",
    "RateLimiter"
]

for a_library in libraries_to_mum:
    the_logger = logging.getLogger(a_library)
    the_logger.setLevel(logging.WARNING)
    the_logger.propagate = True



app = Flask(__name__)
app.debug = True

# database stuff
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_POOL_SIZE"] = 60


db = SQLAlchemy(app)

from models import profile
from models import repo
db.create_all()
db.session.commit()


# from http://docs.sqlalchemy.org/en/latest/core/pooling.html
# This recipe will ensure that a new Connection will succeed even if connections in the pool 
# have gone stale, provided that the database server is actually running. 
# The expense is that of an additional execution performed per checkout
@event.listens_for(Pool, "checkout")
def ping_connection(dbapi_connection, connection_record, connection_proxy):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT 1")
    except:
        # optional - dispose the whole pool
        # instead of invalidating one at a time
        # connection_proxy._pool.dispose()

        # raise DisconnectionError - pool will try
        # connecting again up to three times before raising.
        raise exc.DisconnectionError()
    cursor.close()



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
