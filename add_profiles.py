from time import time
from app import db
from util import elapsed
from models.person import add_profile

from models.profile import add_profile_for_campaign
from models.profile import clean_orcid
from models.profile import NoOrcidException

# needs to be imported so the definitions get loaded into the registry
import job_definitions


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def save_orcids(filename, campaign_name):
    print "saving ORCIDs from {}".format(filename)
    total_start = time()
    with open("data/" + filename, "r") as f:
        lines = f.read().split("\n")
        print "found {} ORCID lines. adding.".format(len(lines))

    for line in lines[:2]:  # take a subset
        start = time()

        if "," in line:
            dirty_orcid, campaign_email = line.split(",")
        else:
            dirty_orcid = line
            campaign_email = None

        try:
            orcid_id = clean_orcid(dirty_orcid)
            print "got orcid_id", orcid_id
        except NoOrcidException:
            print "no valid orcid_id; skipping"
            continue

        print "adding {}...".format(orcid_id)
        add_profile_for_campaign(orcid_id, campaign_email, campaign_name)
        print "done in {}s".format(elapsed(start))

    print "added all ORCIDs in this file in {}".format(
        elapsed(total_start)
    )




if __name__ == "__main__":
    start = time()

    # testing
    save_orcids("orcids_impactstory_no_stripe.txt", "week -1")



    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


