from time import time
from app import db
from util import elapsed
import argparse

from models.person import add_profile_for_campaign
from models.orcid import clean_orcid
from models.orcid import NoOrcidException

# needs to be imported so the definitions get loaded into the registry
import job_definitions


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def load_campaign(filename, campaign_name, limit=None):

    with open("data/" + filename, "r") as f:
        lines = f.read().split("\n")
        print "found {} ORCID lines".format(len(lines))

    if limit:
        lines = lines[:limit]

    for line in lines:
        start = time()

        if "," in line:
            dirty_orcid, campaign_email = line.split(",")
        else:
            dirty_orcid = line
            campaign_email = None

        try:
            orcid_id = clean_orcid(dirty_orcid)
        except NoOrcidException:
            print "no valid orcid_id; skipping"
            continue

        add_profile_for_campaign(orcid_id, campaign_email, campaign_name)

        print "done in {}s".format(elapsed(start))





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many lines to import")
    parsed = parser.parse_args()

    start = time()
    load_campaign("orcids_impactstory_no_stripe.txt", "week -1", limit=parsed.limit)
    print "added all ORCIDs in this file in {}".format(elapsed(start))

    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


