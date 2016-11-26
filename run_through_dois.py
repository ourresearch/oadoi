import argparse
from time import time

from publication import get_pub_from_biblio
from util import elapsed

# do this to get all env variables in console
# set -o allexport
# source conf-file
# set +o allexport

def run_through_dois(first=None, last=None, filename=None):
    total_start = time()
    i = 0
    fh = open(filename, "r")
    has_more_records = True
    for line in fh:
        doi = line.strip()
        my_pub = get_pub_from_biblio({"doi": doi}, force_refresh=False)
        print u"*** {}. {} {}".format(i, my_pub.doi, my_pub.has_fulltext_url)
        i += 1
        print u"finished {} in {}s".format(i, elapsed(total_start, 2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")


    # just for updating lots
    function = run_through_dois
    parser.add_argument('--filename', nargs="?", type=str, help="filename with dois, one per line")
    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first ListRecords.14461")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last ListRecords.14461)")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

