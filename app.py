from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.compress import Compress
from flask_debugtoolbar import DebugToolbarExtension

from sqlalchemy import exc
from sqlalchemy import event
from sqlalchemy import func
from sqlalchemy.pool import Pool

from util import safe_commit
from util import elapsed

import logging
import sys
import os
import requests
import time
from collections import defaultdict

# set up logging
# see http://wiki.pylonshq.com/display/pylonscookbook/Alternative+logging+configuration
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(name)s - %(message)s'
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

requests.packages.urllib3.disable_warnings()

app = Flask(__name__)
# app.debug = True

# database stuff
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True  # as instructed, to supress warning
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_POOL_SIZE"] = 60
app.config['SQLALCHEMY_ECHO'] = (os.getenv("SQLALCHEMY_ECHO", False) == "True")
db = SQLAlchemy(app)

# do compression.  has to be above flask debug toolbar so it can override this.
compress_json = os.getenv("COMPRESS_DEBUG", "False")=="True"

# set up Flask-DebugToolbar
if (os.getenv("FLASK_DEBUG", False) == "True"):
    logger.info("Setting app.debug=True; Flask-DebugToolbar will display")
    compress_json = False
    app.debug = True
    app.config['DEBUG'] = True
    app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False
    app.config["SQLALCHEMY_RECORD_QUERIES"] = True
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    toolbar = DebugToolbarExtension(app)

# gzip responses
Compress(app)
app.config["COMPRESS_DEBUG"] = compress_json


# for running rq jobs
ti_queues = []

# commented out because no queues right now because not using RQ
# for i in range(0, 10):
#     ti_queues.append(
#         Queue("ti-queue-{}".format(i), connection=redis_rq_conn)
#     )


# imports got here for tables that need auto-created.
# from models import temp_orcid_profile
# from models import temp_product
#
# from models import product
# from models import person
# from models import badge
#
# db.create_all()
# commit_success = safe_commit(db)
# if not commit_success:
#     print u"COMMIT fail making objects"


# This takes a while.  Do it here so is part of expected boot-up.

def shortcut_all_percentile_refsets():
    refsets = shortcut_score_percentile_refsets()
    refsets.update(shortcut_badge_percentile_refsets())
    return refsets

def size_of_refset():
    from models.person import Person

    # from https://gist.github.com/hest/8798884
    count_q = db.session.query(Person).filter(Person.campaign == "2015_with_urls")
    count_q = count_q.statement.with_only_columns([func.count()]).order_by(None)
    count = db.session.execute(count_q).scalar()
    print "refsize count", count
    return count

def shortcut_score_percentile_refsets():
    from models.person import Person

    print u"getting the score percentile refsets...."
    refset_list_dict = defaultdict(list)
    q = db.session.query(
        Person.buzz,
        Person.influence,
        Person.openness
    )
    q = q.filter(Person.score != 0)
    rows = q.all()

    num_in_refset = size_of_refset()

    print u"query finished, now set the values in the lists"
    refset_list_dict["buzz"] = [row[0] for row in rows if row[0] != None]
    refset_list_dict["buzz"].extend([0] * (num_in_refset - len(refset_list_dict["buzz"])))

    refset_list_dict["influence"] = [row[1] for row in rows if row[1] != None]
    refset_list_dict["influence"].extend([0] * (num_in_refset - len(refset_list_dict["influence"])))

    refset_list_dict["openness"] = [row[2] for row in rows if row[2] != None]
    # don't zero pad this one!

    for name, values in refset_list_dict.iteritems():
        # now sort
        refset_list_dict[name] = sorted(values)

    return refset_list_dict


def shortcut_badge_percentile_refsets():
    from models.badge import Badge
    from models.badge import get_badge_assigner

    print u"getting the badge percentile refsets...."
    refset_list_dict = defaultdict(list)
    q = db.session.query(
        Badge.name,
        Badge.value,
    )
    q = q.filter(Badge.value != None)
    rows = q.all()

    print u"query finished, now set the values in the lists"
    for row in rows:
        if row[1]:
            refset_list_dict[row[0]].append(row[1])

    num_in_refset = size_of_refset()

    for name, values in refset_list_dict.iteritems():

        if get_badge_assigner(name).pad_percentiles_with_zeros:
            # pad with zeros for all the people who didn't get the badge
            values.extend([0] * (num_in_refset - len(values)))

        # now sort
        refset_list_dict[name] = sorted(values)

    return refset_list_dict

refsets = None
start_time = time.time()
if os.getenv("IS_LOCAL", False):
    print u"Not loading refsets because IS_LOCAL. Will not set percentiles when creating or refreshing profiles."
else:
    refsets = shortcut_badge_percentile_refsets()
    refsets.update(shortcut_score_percentile_refsets())
print u"finished with refsets in {}s".format(elapsed(start_time))


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






