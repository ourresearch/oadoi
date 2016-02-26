from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError

from app import db

from models import product  # needed for sqla i think
from models import orcid
from models.orcid import OrcidProfile
from models.product import make_product
from models.product import NoDoiException

import jwt
import twitter
import os
import shortuuid
import requests
import json
import re
from datetime import datetime
from datetime import timedelta
from util import elapsed
from time import time
from collections import defaultdict



def make_person_from_google(person_dict):
    print "\n\nmaking new person with person_dict: ", person_dict, "\n\n"
    new_person = Person(
        email=person_dict["email"],
        given_name=person_dict["given_name"],
        family_name=person_dict["family_name"],
        picture=person_dict["picture"],
        oauth_source='google',
        oauth_api_raw=person_dict
    )

    db.session.add(new_person)
    db.session.commit()

    return new_person


def add_or_overwrite_profile(id, sample_name=None):

    my_orcid = OrcidProfile(orcid_id)

    # if one already there, use it and overwrite.  else make a new one.
    my_profile = Person.query.filter_by(orcid_id=orcid_id).first()
    if not my_profile:
        my_profile = Person(orcid_id=orcid_id)
    my_profile.given_names_orcid = my_orcid.given_names
    my_profile.family_name_orcid = my_orcid.family_name
    my_profile.api_raw = json.dumps(my_orcid.api_raw)

    for work in my_orcid.works:
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
        print "this person already exists. setting the sample and overwriting."
        db.session.rollback()

        if sample_name:
            my_profile.sample[sample_name] = True

        db.session.merge(my_profile)
        db.session.commit()

    return my_profile


class Person(db.Model):
    id = db.Column(db.Text, primary_key=True)
    orcid_id = db.Column(db.Text, unique=True)
    email = db.Column(db.Text)
    given_name = db.Column(db.Text)
    family_name = db.Column(db.Text)
    picture = db.Column(db.Text)

    oauth_source = db.Column(db.Text)
    oauth_api_raw = db.Column(JSONB)

    given_names_orcid = db.Column(db.Text)
    family_name_orcid = db.Column(db.Text)
    api_raw = db.Column(db.Text)

    t_index = db.Column(db.Integer)
    num_products = db.Column(db.Integer)

    metric_sums = db.Column(MutableDict.as_mutable(JSONB))
    num_with_metrics = db.Column(MutableDict.as_mutable(JSONB))
    num_sources = db.Column(db.Integer)

    altmetric_score = db.Column(db.Float)
    monthly_event_count = db.Column(db.Float)

    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("person", lazy="subquery"),
        foreign_keys="Product.orcid_id"
    )

    def __init__(self, **kwargs):
        shortuuid.set_alphabet('abcdefghijklmnopqrstuvwxyz1234567890')
        self.id = shortuuid.uuid()[0:24]
        super(Person, self).__init__(**kwargs)


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

    def set_monthly_event_count(self):
        self.monthly_event_count = 0
        counter = defaultdict(int)

        for product in self.products:
            if product.event_dates:
                for event_date in product.event_dates:
                    for month_string in ["2015-10", "2015-11", "2015-12"]:
                        if event_date.startswith(month_string):
                            counter[month_string] += 1

        try:
            self.monthly_event_count = min(counter.values())
        except ValueError:
            pass # no events

        print "setting events in last 3 months as {}".format(self.monthly_event_count)


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


    def get_token(self):
        payload = {
            'sub': self.email,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(days=999),
            'picture': self.picture
        }
        token = jwt.encode(payload, os.getenv("JWT_KEY"))
        return token.decode('unicode_escape')



    def __repr__(self):
        return u'<Person ({id}, {orcid_id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            orcid_id=self.orcid_id,
            given_names=self.given_names,
            family_name=self.family_name
        )


    def to_dict_orcid(self):
        return {
            "id": self.id,
            "orcid_id": self.orcid_id,
            "given_names": self.given_names_orcid,
            "family_name": self.family_name_orcid,
            "metric_sums": self.metric_sums,
            "monthly_event_count": self.monthly_event_count,
            "products": [p.to_dict() for p in self.products]
        }


    def to_dict(self):
        return {
            "email": self.email,
            "given_names": self.given_name,
            "family_name": self.family_name,
            "picture": self.picture,
            "orcid_id": self.orcid_id
        }


def h_index(citations):
    # from http://www.rainatian.com/2015/09/05/leetcode-python-h-index/

    citations.sort(reverse=True)

    i=0
    while (i<len(citations) and i+1 <= citations[i]):
        i += 1

    return i
