from time import time
from app import db
from util import elapsed
from util import safe_commit
import argparse

from models.person import add_or_overwrite_person_from_orcid_id
from models.orcid import clean_orcid
from models.orcid import NoOrcidException

# needs to be imported so the definitions get loaded into the registry
import jobs_defs


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def create_person(dirty_orcid, campaign=None):

    try:
        orcid_id = clean_orcid(dirty_orcid)
    except NoOrcidException:
        print u"\n\nWARNING: no valid orcid_id in {}; skipping\n\n".format(dirty_orcid)
        raise

    my_person = add_or_overwrite_person_from_orcid_id(orcid_id, high_priority=False)

    if campaign:
        my_person.campaign = campaign
        db.session.add(my_person)
        success = safe_commit(db)
        if not success:
            print u"ERROR!  committing {}".format(my_person.orcid_id)




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('orcid_id', type=str, help="ORCID ID to build")
    parser.add_argument('--campaign', type=str, help="name of campaign")
    parsed = parser.parse_args()

    start = time()
    create_person(parsed.orcid_id, parsed.campaign)

    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


