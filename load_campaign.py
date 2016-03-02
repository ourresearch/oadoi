from time import time
from app import db
from util import elapsed
import argparse

from models.person import add_or_overwrite_person_from_orcid_id
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
            try:
                print u"\n\nWARNING: no valid orcid_id in line {}; skipping\n\n".format(line)
            except UnicodeDecodeError:
                print u"\n\nWARNING: no valid orcid_id and line throws UnicodeDecodeError; skipping\n\n"
            continue

        add_or_overwrite_person_from_orcid_id(orcid_id, campaign_email, campaign_name, high_priority=False)

    print "loaded {} profiles in {}s\n".format(len(lines), elapsed(start))





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many lines to import")
    parsed = parser.parse_args()

    start = time()
    load_campaign("orcids_impactstory_has_stripe.txt", "impactstory_has_stripe", limit=parsed.limit)

    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


