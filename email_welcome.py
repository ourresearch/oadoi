from time import time
from util import elapsed
from util import safe_commit
import argparse

from models import emailer
from collections import defaultdict


"""
Call from command line to add ORCID profiles based on IDs in a local CSV.

"""


def email_everyone(filename):

    with open(filename, "r") as f:
        lines = f.read().split("\n")
        print "found {} lines".format(len(lines))

    total_start = time()
    row_num = 0
    people_to_email = defaultdict(dict)

    # skip header row
    for line in lines[1:]:
        row_num += 1

        try:
            (url_slug,orcid_id,twitter_id,email,stripe_id,is_advisor,given_name,surname,created,last_viewed_profile) = line.split(",")

            is_subscribed = len(stripe_id)>0 or is_advisor=="t"

            people_to_email[email] = {
                "orcid_id": orcid_id,
                "is_subscribed": is_subscribed,
                "given_name": given_name,
                "surname": surname,
                "refunded": False
            }
            print u"added person {} {} {}".format(row_num, email, people_to_email[email])
        except ValueError:
            print u"couldn't parse", line

    with open("data/impactstory_refunds.csv", "r") as f:
        lines = f.read().split("\r")
        print "found {} lines".format(len(lines))

    for line in lines[1:]:
        try:
            (stripe_created,full_name,email) = line.split(",")
            if email in people_to_email:
                people_to_email[email]["refunded"] = True
                print "added refunded true to dict for", email
            else:
                people_to_email[email] = {
                    "orcid_id": None,
                    "is_subscribed": False,
                    "refunded": False
                }
                print "added new emailee true to dict for", email
        except ValueError:
            print "couldn't parse"

    email = "heather@impactstory.org"
    send_tng_email("heather@impactstory.org", people_to_email[email])

    for email, addressee_dict in people_to_email.iteritems():
        # print ",",
        # send_tng_email(email, addressee_dict)
        pass


def send_tng_email(email, addressee_dict, now=None):

    # if os.getenv("ENVIRONMENT", "testing") == "production":
    #     email = profile.email
    # else:
    #     email = "heather@impactstory.org"

    report_dict = {"profile": addressee_dict}

    #### KEEEP THIS HERE FOR NOW, so that don't spam other people
    email = 'hpiwowar@gmail.com'

    msg = emailer.send(email, "Big exciting changes: New Impactstory!", "welcome", report_dict)

    print "SENT EMAIL to ", email





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('filename', type=str, help="filename to import")
    parsed = parser.parse_args()

    start = time()
    email_everyone(parsed.filename)
    print "finished update in {}sec".format(elapsed(start))


