from time import time
from app import db
from util import elapsed
from util import safe_commit
import argparse

from models.person import add_or_overwrite_person_from_orcid_id
from models.person import make_person
from models.person import Person
from models.orcid import clean_orcid
from models.orcid import NoOrcidException

# needs to be imported so the definitions get loaded into the registry
import jobs_defs


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def load_campaign(filename, campaign=None, limit=None):

    with open("data/" + filename, "r") as f:
        lines = f.read().split("\n")
        print "found {} ORCID lines".format(len(lines))

    print "hi heather"
    print len(lines)

    if limit:
        lines = lines[:limit]


    total_start = time()
    for line in lines:

        # can have # as comments
        if line.startswith("#"):
            print "skipping comment line"
            continue

        loop_start = time()
        email = None

        if "," in line:
            (dirty_orcid, email) = line.split(",")
        else:
            dirty_orcid = line

        try:
            orcid_id = clean_orcid(dirty_orcid)
        except NoOrcidException:
            try:
                print u"\n\nWARNING: no valid orcid_id in line {}; skipping\n\n".format(line)
            except UnicodeDecodeError:
                print u"\n\nWARNING: no valid orcid_id and line throws UnicodeDecodeError; skipping\n\n"
            continue

        my_person = Person.query.filter_by(orcid_id=orcid_id).first()
        if my_person:
            print u"already have person {}, skipping".format(orcid_id)
        else:
            my_person = make_person(orcid_id, high_priority=False)
            my_person.campaign = campaign
            my_person.email = email
            db.session.merge(my_person)
            commit_success = safe_commit(db)
            if not commit_success:
                print u"COMMIT fail on {}".format(my_person.orcid_id)

        print "loaded {} in {}s\n".format(orcid_id, elapsed(loop_start))

    print "loaded {} profiles in {}s\n".format(len(lines), elapsed(total_start))



def just_add_twitter(filename, limit=None, create=True):

    with open("data/" + filename, "r") as f:
        lines = f.read().split("\n")
        print "found {} ORCID lines".format(len(lines))

    if limit:
        lines = lines[:limit]

    total_start = time()
    for line in lines:

        loop_start = time()

        email = None
        twitter = None

        if "," in line:
            (dirty_orcid, email, twitter) = line.split(",")
        else:
            dirty_orcid = line

        if twitter:
            twitter = twitter.replace("@", "")
            try:
                orcid_id = clean_orcid(dirty_orcid)
            except NoOrcidException:
                try:
                    print u"\n\nWARNING: no valid orcid_id in line {}; skipping\n\n".format(line)
                except UnicodeDecodeError:
                    print u"\n\nWARNING: no valid orcid_id and line throws UnicodeDecodeError; skipping\n\n"
                continue

            my_person = Person.query.filter_by(orcid_id=orcid_id).first()
            if my_person:
                my_person.twitter = twitter
                db.session.merge(my_person)
                commit_success = safe_commit(db)
                if not commit_success:
                    print u"COMMIT fail on {}".format(orcid_id)
                print u"added twitter {} to {}".format(twitter, orcid_id)
            else:
                print u"no person found with id {}".format(orcid_id)


    print "loaded {} profiles in {}s\n".format(len(lines), elapsed(total_start))





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('file_name', type=str, help="filename to import")
    parser.add_argument('campaign', type=str, help="name of campaign")
    parser.add_argument('--limit', "-l", nargs="?", type=int, help="how many lines to import")
    parser.add_argument('--just_add_twitter', nargs="?", type=bool, default=False, help="just add twitter")
    parsed = parser.parse_args()

    start = time()
    if parsed.just_add_twitter:
        just_add_twitter(parsed.file_name, limit=parsed.limit)
    else:
        load_campaign(parsed.file_name, campaign=parsed.campaign, limit=parsed.limit)

    db.session.remove()
    print "finished update in {}sec".format(elapsed(start))


