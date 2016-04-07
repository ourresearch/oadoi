from time import time
from app import db
from util import elapsed
from util import safe_commit
import argparse
import pickle
from pathlib import Path

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


def save_refsets():
    data_dir = Path(__file__, "../data").resolve()

    start = time()
    print "loading badge refsets"
    badge_refsets = Person.shortcut_badge_percentile_refsets()
    print(len(badge_refsets))
    print "loaded badge refsets in {}s\n".format(elapsed(start))
    badge_pickle_path = Path(data_dir, "badge_refsets.pickle")
    with open(str(badge_pickle_path), "w") as f:
        pickle.dump(badge_refsets, f)

    start = time()
    print "loading score refsets"
    score_refsets = Person.shortcut_score_percentile_refsets()
    print(len(score_refsets))
    print "loaded score refsets in {}s\n".format(elapsed(start))
    score_pickle_path = Path(data_dir, "score_refsets.pickle")
    with open(str(score_pickle_path), "w") as f:
        pickle.dump(score_refsets, f)



if __name__ == "__main__":
    total_start = time()

    parser = argparse.ArgumentParser(description="Run stuff.")

    save_refsets()

    print "finished in {}sec".format(elapsed(total_start))


