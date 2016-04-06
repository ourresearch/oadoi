from time import time
from collections import defaultdict
import argparse
import os
import datetime
import stripe
import requests.packages.urllib3
import pprint

from util import elapsed


"""
refund payments

"""

resp = defaultdict(int)

def run_on_charges(charge):
    resp["total"] += 1
    if charge.refunded:
        resp["refunded"] += 1
    if charge.paid:
        resp["paid"] += 1

    resp[charge.amount] += 1

    today = datetime.datetime.today()
    charge_date = datetime.datetime.fromtimestamp(charge.created)
    days_since_charge = (charge_date - today).days
    if days_since_charge < 365:
        resp["in_last_year"] += 1

    if not charge.refunded and (days_since_charge < 365):
        print "refunding: ", charge.id
        charge.refund(metadata={"reason": "switch to TNG"})



def refund_cards():
    num_charges = 0
    charges = stripe.Charge.all(limit=100)

    for charge in charges.data:
        print ".",
        num_charges += 1
        run_on_charges(charge)

    while charges.has_more:
        charges = stripe.Charge.all(limit=100, starting_after=charges.data[-1])
        for charge in charges.data:
            print ".",
            num_charges += 1
            run_on_charges(charge)

    pprint.pprint(dict(resp))
    print "num_charges=", num_charges


def run_on_customer(customer):
    # cancel subscription
    if customer.subscriptions:
        print "would cancel subscription", customer.id
        # customer.cancel_subscription()

    cards = stripe.Customer.retrieve(customer.id).sources.all(object="card")
    for card in cards.data:
        print "would delete card", customer.id, card.id
        # card.delete()

def cancel_subscriptions_and_delete_cards():
    num_customers = 0
    customers = stripe.Customer.all(limit=50)

    for customer in customers.data:
        print ".",
        num_customers += 1
        run_on_customer(customer)

    while customers.has_more:
        customers = stripe.Customer.all(limit=50, starting_after=customers.data[-1])
        for customer in customers.data:
            print ".",
            num_customers += 1
            run_on_customer(customer)

    print "num_customers=", num_customers


# # another way to delete all the cards, if find there are still some cards in stripe
# try:
#     customer_id = charge.card.customer
#     card_id = charge.card.id
#     customer = stripe.Customer.retrieve(customer_id)
#     # customer.sources.retrieve(card_id).delete()
# except stripe.error.InvalidRequestError:
#     print "GOT A STRIPE ERROR on charge", charge.id



if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()

    start = time()

    stripe.api_key = os.getenv("STRIPE_API_KEY")

    refund_cards()
    # cancel_subscriptions_and_delete_cards()

    print "finished script in {}sec".format(elapsed(start))


