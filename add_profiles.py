from time import time
from app import db
from util import elapsed
from models.profile import add_profile


# needs to be imported so the definitions get loaded into the registry
import job_definitions


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def save_orcids(filename, sample_name):
    print "saving ORCIDs from {}".format(filename)
    total_start = time()
    with open("data/" + filename, "r") as f:
        orcids = f.read().split("\n")
        print "found {} ORCIDs. adding.".format(len(orcids))

    for orcid in orcids[0:99]:  # just take the first 100 IDs...
        start = time()
        print "adding {}...".format(orcid)
        add_profile(orcid, sample_name)
        print "done in {}s".format(elapsed(start))

    print "added all ORCIDs in this file in {}".format(
        elapsed(total_start)
    )




if __name__ == "__main__":
    start = time()

    save_orcids("orcid_researches_twitter.txt", "social_media_researchers")



    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


