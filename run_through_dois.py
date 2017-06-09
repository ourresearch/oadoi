import argparse
from time import time
import json
from sqlalchemy.dialects.postgresql import JSONB
import urllib
import requests
from sqlalchemy.orm.attributes import flag_modified

from util import elapsed
from util import clean_doi
from util import safe_commit
from util import NoDoiException

from app import db

# create table dois_random_recent (doi text)
# psql `heroku config:get DATABASE_URL`?ssl=true -c "\copy dois_random_recent FROM 'data/random_dois_recent.txt';"
# select doi, 'http://doi.org/'||doi as doi_url, their_url,
# content->>'free_fulltext_url' as our_url, content->>'oa_color' as oa_color, content->>'is_subscription_journal' as is_subscription_journal
# from dois_oab, cached where doi=id


class Oab(db.Model):
    id = db.Column(db.Text, primary_key=True)
    api = db.Column(JSONB)
    dissemin = db.Column(JSONB)


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
        dois.append(line.strip())

        # line = line.replace('"', '')
        # if u"," in line:
        #     split_line = line.split(",")
        #     if loggly:
        #         dois.append(split_line[1])
        #     else:
        #         dois.append(split_line[0])
        # else:
        #     dois.append(line.strip())

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

        if not my_doi:
            print "bad doi: {}".format(doi)
            continue

        my_pub = Oab.query.get(my_doi)
        if not my_pub:
            my_pub = Oab()
            db.session.add(my_pub)
        my_pub.id = my_doi
        my_doi_url = "http://doi.org/{}".format(my_doi)
        my_doi_url_encoded = urllib.quote_plus(my_doi_url)
        api_url = "https://api.openaccessbutton.org/availability?url={}".format(my_doi_url_encoded)
        headers = {"content-type": "application/json"}
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            print "success with oab! with {}".format(my_doi)
            # print r.json()
            my_pub.api = r.json()
            flag_modified(my_pub, "api")
        else:
            print "problem with oab, status_code {}".format(r.status_code)

        dissemin_url = "http://dissem.in/api/{}".format(my_doi)
        r = requests.get(dissemin_url, headers=headers)
        if r.status_code == 200:
            print "success! with dissemin! with {}".format(my_doi)
            # print r.json()
            my_pub.dissemin = r.json()
            flag_modified(my_pub, "dissemin")
        else:
            print "problem with dissemin, status_code {}".format(r.status_code)

        safe_commit(db)
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

