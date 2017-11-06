import argparse
from time import time
import requests
from sqlalchemy import sql

from publication import get_pub_from_biblio
from util import elapsed
from app import db
from app import logger

# do this to get all env variables in console
# source .env

def get_dois(limit):
    q = u"""select id from pub where response is null limit {}""".format(limit)
    rows = db.engine.execute(sql.text(q)).fetchall()
    dois = [row[0] for row in rows]
    return dois

def call_oadoi(doi):
    start_time = time()
    r = requests.get("http://api.oadoi.org/{}?email=loadtest@impactstory.org&hybrid".format(doi))
    r = requests.get("https://oadoi-staging.herokuapp.com/{}?email=loadtest@impactstory.org&hybrid".format(doi))
    logger.info(u"took {} seconds for {}".format(elapsed(start_time, 2), doi))
    return r

def run_through_dois(limit):
    for doi in get_dois(limit):
        r = call_oadoi(doi)
        if r.status_code != 200:
            logger.info(u"ERROR: {}".format(r.status_code))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")


    # just for updating lots
    function = run_through_dois
    parser.add_argument('--limit', nargs="?", type=int, default=10000, help="number to run")

    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    run_through_dois(parsed.limit)

