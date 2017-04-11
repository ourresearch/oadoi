import argparse
from time import time
import json

from publication import Crossref
from util import elapsed
from util import clean_doi
from util import NoDoiException

# create table dois_random_recent (doi text)
# psql `heroku config:get DATABASE_URL`?ssl=true -c "\copy dois_random_recent FROM 'data/random_dois_recent.txt';"
# select doi, 'http://doi.org/'||doi as doi_url, their_url,
# content->>'free_fulltext_url' as our_url, content->>'oa_color' as oa_color, content->>'is_subscription_journal' as is_subscription_journal
# from dois_oab, cached where doi=id



def run_through_dois(filename=None, reverse=None, loggly=False):
    total_start = time()
    i = 0
    output_dicts = []
    fh = open(filename, "r")

    lines = fh.readlines()

    if reverse:
        print "reverse!"
        lines.reverse()
        i = -1 * len(lines)

    dois = []
    for line in lines:
        line = line.replace('"', '')
        if u"," in line:
            split_line = line.split(",")
            if loggly:
                dois.append(split_line[1])
            else:
                dois.append(split_line[0])
        else:
            dois.append(line.strip())

    # deduplicate, preserving order
    duplicated_dois = dois
    dois = []
    for doi in duplicated_dois:
        if doi not in dois:
            dois.append(doi)

    print "length of deduped doi list: {}".format(len(dois))

    for doi in dois:

        try:
            my_doi = clean_doi(doi)
        except NoDoiException:
            print "bad doi: {}".format(doi)
            continue

        my_pub = Crossref.query.get(my_doi)
        if my_pub:
            my_pub.refresh(quiet=True)
            if i < 1:
                print "|", u"|".join(my_pub.learning_header())
            print "|", u"|".join(my_pub.learning_row())

        i += 1

    print u"finished {} in {} seconds".format(i, elapsed(total_start, 2))

    fh_out.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    function = run_through_dois
    parser.add_argument('--filename', nargs="?", type=str, help="filename with dois, one per line")
    parser.add_argument('--reverse', nargs="?", default=False, type=bool,
                            help="call to start at the bottom of the file and run through in reverse")
    parser.add_argument('--loggly', nargs="?", type=bool, default=False, help="assumes the doi is the second column, timestamp is first")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

