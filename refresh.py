from time import time
from app import db
from util import elapsed
from util import safe_commit
import argparse

from models.orcid import clean_orcid
from models.orcid import NoOrcidException
from models.person import refresh_profile

# needs to be imported so the definitions get loaded into the registry
import jobs_defs


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def refresh(orcid_id):

    try:
        orcid_id = clean_orcid(dirty_orcid)
    except NoOrcidException:
        print u"\n\nWARNING: no valid orcid_id in {}; skipping\n\n".format(dirty_orcid)
        raise

    refresh_profile(orcid_id)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('orcid_id', type=str, help="ORCID ID to build")
    parsed = parser.parse_args()

    start = time()
    refresh(parsed.orcid_id)

    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


