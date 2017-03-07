import argparse
from time import time

from publication import get_pub_from_biblio
from util import elapsed

# do this to get all env variables in console
# source .env

# create table dois_oab (doi text, their_url text)
# psql `heroku config:get DATABASE_URL`?ssl=true -c "\copy dois_oab FROM 'oab.csv' WITH CSV;"

# select doi, 'http://doi.org/'||doi as doi_url, their_url,
# content->>'free_fulltext_url' as our_url, content->>'oa_color' as oa_color, content->>'is_subscription_journal' as is_subscription_journal
# from dois_oab, cached where doi=id

def run_through_dois(first=None, last=None, filename=None, reverse=None):
    total_start = time()
    i = 0
    fh = open(filename, "r")
    has_more_records = True

    lines = fh.readlines()
    if reverse:
        print "reverse!"
        lines.reverse()
        i = -1 * len(lines)

    for line in lines:
        line = line.strip()
        split_line = line.split(",")
        doi = split_line[0]
        my_pub = get_pub_from_biblio({"doi": doi}, force_refresh=True)
        if len(split_line) > 1:
            try:
                url = split_line[1]
                if url==my_pub.best_redirect_url:
                    print u"{} yay found the url we were looking for! {}\n".format(i, url)
                # else:
                #     print u"{} hrm was looking for {} but found {} for doi {}\n".format(
                #         i, url, my_pub.best_redirect_url, doi)
            except (KeyboardInterrupt, SystemExit):
                return
            except Exception:
                pass
        else:
            print u"*** {}. {}".format(i, my_pub.id)
        i += 1
        print u"finished {} in {} seconds".format(i, elapsed(total_start, 2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")


    # just for updating lots
    function = run_through_dois
    parser.add_argument('--filename', nargs="?", type=str, help="filename with dois, one per line")
    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first ListRecords.14461")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last ListRecords.14461)")
    parser.add_argument('--reverse', nargs="?", default=False, type=bool,
                            help="call to start at the bottom of the file and run through in reverse")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

