import argparse
import requests
from time import time
from random import shuffle

from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import ti_queues
from util import elapsed
from util import safe_commit

# do this to get all env variables in console
# source .env



class DoiResult(db.Model):
    id = db.Column(db.Text, primary_key=True)
    result = db.Column(JSONB)

    def __init__(self, doi):
        self.doi = doi


    def articlepage(self):
        url_base = u"http://api.articlepage.org/doi/{}"
        url = url_base.format(self.doi)

        print u"hitting {}".format(url)
        start = time()

        # res = requests.get(url)
        # self.result = res.json()

        print u"finished {} in {} seconds".format(self.doi, elapsed(start))

        return True


def save_doi_result(doi):
    doi_result = DoiResult(doi)

    # run the function. you can pass the function name in
    # later, but for now am hardcoding it in.
    fn_result = getattr(doi_result, "articlepage")()

    commit_success = safe_commit(db)
    if commit_success:
        print u"saved results for {}".format(doi)
    else:
        print u"OH NOES commit fail on {}".format(doi)

    db.session.remove()  # close connection nicely


    return None  # important for if we use this on RQ



def run_through_dois(filename, queue_number=0):
    total_start = time()
    i = 0

    doi_queue = ti_queues[queue_number]
    num_jobs = doi_queue.count
    doi_queue.empty()
    print u"emptied {} jobs from doi_queue".format(num_jobs)

    fh = open(filename, "r")
    lines = fh.readlines()

    # the list is sorted by publisher, which we don't want.
    # randomizing makes sure we are not hitting any one publisher
    # too hard all at once with the scraper.
    shuffle(lines)

    for line in lines:
        doi = line.strip()

        # enqueue here
        doi_queue.enqueue(
            func=save_doi_result,
            args=[doi],
            timeout=60 * 10,
            result_ttl=0
        )

        i += 1
        print u"enqueued {} DOIs in {} seconds".format(i, elapsed(total_start, 2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('--filename', nargs="?", type=str, help="filename with dois, one per line")

    parsed = parser.parse_args()

    print u"Running through DOIs"
    run_through_dois(parsed["filename"])


