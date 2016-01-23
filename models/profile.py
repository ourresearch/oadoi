from app import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError

from models import product  # needed for sqla i think
from models.product import make_product
from models.product import NoDoiException
from util import elapsed
from time import time

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

    def set_t_index(self):
        my_products = self.products

        tweet_counts = []
        for p in my_products:
            try:
                int(tweet_counts.append(p.altmetric_counts["tweeters"]))
            except KeyError:
                tweet_counts.append(0)

        self.t_index = h_index(tweet_counts)

        print "t-index={t_index} based on {total} tweeted products ({tweeted_count} total)".format(
            t_index=self.t_index,
            total=len(my_products),
            tweeted_count=len([x for x in tweet_counts if x])
        )

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
    """
    from http://www.rainatian.com/2015/09/05/leetcode-python-h-index/

    :type citations: List[int]
    :rtype: int
    """

    citations.sort(reverse=True)

    i=0
    while (i<len(citations) and i+1 <= citations[i]):
        i += 1

    return i


