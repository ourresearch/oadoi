from app import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError

from models import product  # needed for sqla i think
from models.product import make_product
from models.product import NoDoiException
from util import elapsed
from time import time
from collections import defaultdict

import requests
import json

def get_orcid_api_raw(orcid):
    headers = {'Accept': 'application/orcid+json'}
    url = "http://pub.orcid.org/{id}/orcid-profile".format(id=orcid)
    start = time()
    r = requests.get(url, headers=headers)
    print "got ORCID details in {elapsed}s for {id}".format(
        id=orcid,
        elapsed=elapsed(start)
    )
    orcid_resp_dict = r.json()
    return orcid_resp_dict["orcid-profile"]

def add_profile(orcid, sample_name=None):

    api_raw = get_orcid_api_raw(orcid)

    try:
        given_names = api_raw["orcid-bio"]["personal-details"]["given-names"]["value"]
    except (TypeError,):
        given_names = None

    try:
        family_name = api_raw["orcid-bio"]["personal-details"]["family-name"]["value"]
    except (TypeError,):
        family_name = None

    try:
        works = api_raw["orcid-activities"]["orcid-works"]["orcid-work"]
        if not works:
            works = []
    except TypeError:
        works = []

    my_profile = Profile(
        id=orcid,
        given_names=given_names,
        family_name=family_name,
        api_raw=json.dumps(api_raw)
    )

    for work in works:
        try:
            my_product = make_product(work)
            my_profile.add_product(my_product)
        except NoDoiException:
            # just ignore this work, it's not a product for our purposes.
            pass

    if sample_name:
        my_profile.sample = {
            sample_name: True
        }

    db.session.add(my_profile)
    try:
        db.session.commit()
    except IntegrityError:
        print "this profile already exists. setting the sample."
        db.session.rollback()

        my_profile = Profile.query.get(orcid)
        my_profile.sample[sample_name] = True

        db.session.merge(my_profile)
        db.session.commit()

    return my_profile


class Profile(db.Model):
    id = db.Column(db.Text, primary_key=True)
    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    api_raw = db.Column(db.Text)
    sample = db.Column(MutableDict.as_mutable(JSONB))

    t_index = db.Column(db.Integer)
    num_products = db.Column(db.Integer)
    metric_sums = db.Column(MutableDict.as_mutable(JSONB))
    num_with_metrics = db.Column(MutableDict.as_mutable(JSONB))
    num_sources = db.Column(db.Integer)

    altmetric_score = db.Column(db.Float)
    events_in_last_3_months = db.Column(db.Float)

    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("profile", lazy="subquery")
    )

    def add_product(self, product_to_add):
        if product_to_add.doi in [p.doi for p in self.products]:
            return False
        else:
            self.products.append(product_to_add)
            return True


    def set_altmetric_stats(self):
        self.set_t_index()
        self.set_metric_sums()
        self.set_num_sources()
        self.set_num_with_metrics()
        self.set_num_products()

    def set_t_index(self):
        my_products = self.products

        tweet_counts = []
        for p in my_products:
            try:
                int(tweet_counts.append(p.altmetric_counts["tweeters"]))
            except (KeyError, TypeError):
                tweet_counts.append(0)

        self.t_index = h_index(tweet_counts)

        print u"t-index={t_index} based on {tweeted_count} tweeted products ({total} total)".format(
            t_index=self.t_index,
            tweeted_count=len([x for x in tweet_counts if x]),
            total=len(my_products)
        )

    def set_events_in_last_3_months(self):
        self.events_in_last_3_months = 0
        counter = defaultdict(int)

        for product in self.products:
            if product.event_dates:
                for event_date in product.event_dates:
                    for month_string in ["2015-10", "2015-11", "2015-12"]:
                        if event_date.startswith(month_string):
                            counter[month_string] += 1

        try:
            self.events_in_last_3_months = min(counter.values())
        except ValueError:
            pass # no events

        print "setting events in last 3 months as {}".format(self.events_in_last_3_months)


    def set_altmetric_score(self):
        self.altmetric_score = 0
        for p in self.products:
            if p.altmetric_score:
                self.altmetric_score += p.altmetric_score
        print u"total altmetric score: {}".format(self.altmetric_score)


    def set_num_products(self):
        self.num_products = len(self.products)
        print "setting {} products".format(self.num_products)

    def set_metric_sums(self):
        if self.metric_sums is None:
            self.metric_sums = {}

        for p in self.products:
            for metric, count in p.altmetric_counts.iteritems():
                try:
                    self.metric_sums[metric] += int(count)
                except KeyError:
                    self.metric_sums[metric] = int(count)

        print "setting metric_sums", self.metric_sums

    def set_num_sources(self):
        if self.metric_sums is None:
            self.metric_sums = {}

        self.num_sources = len(self.metric_sums.keys())

    def set_num_with_metrics(self):
        if self.num_with_metrics is None:
            self.num_with_metrics = {}

        for p in self.products:
            for metric, count in p.altmetric_counts.iteritems():
                try:
                    self.num_with_metrics[metric] += 1
                except KeyError:
                    self.num_with_metrics[metric] = 1

        print "setting num_with_metrics", self.num_with_metrics


    def __repr__(self):
        return u'<Profile ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names,
            family_name=self.family_name
        )

    def to_dict(self):
        return {
            "id": self.id,
            "given_names": self.given_names,
            "family_names": self.family_name,
            "products": [p.to_dict() for p in self.products]

        }


def h_index(citations):
    # from http://www.rainatian.com/2015/09/05/leetcode-python-h-index/

    citations.sort(reverse=True)

    i=0
    while (i<len(citations) and i+1 <= citations[i]):
        i += 1

    return i


