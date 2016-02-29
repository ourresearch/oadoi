from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError

from app import db

from models import product  # needed for sqla i think
from models.orcid import OrcidProfile
from models.product import make_product
from models.product import NoDoiException
from models.orcid import make_and_populate_orcid_profile

import jwt
import twitter
import os
import shortuuid
import requests
import json
import re
import datetime
import logging
import operator
import threading
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





def add_or_overwrite_person_from_orcid_id(orcid_id,
                                          campaign_email=None,
                                          campaign=None,
                                          high_priority=False):

    # if one already there, use it and overwrite.  else make a new one.
    my_profile = Person.query.filter_by(orcid_id=orcid_id).first()
    if my_profile:
        db.session.merge(my_profile)
    else:
        # make a person with this orcid_id
        my_profile = Person(orcid_id=orcid_id)
        db.session.add(my_profile)

    # set the campaign name and email it came in with (if any)
    my_profile.campaign = campaign
    my_profile.campaign_email = campaign_email

    my_profile.refresh(high_priority=high_priority)

    # now write to the db
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

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    error = db.Column(db.Text)

    campaign = db.Column(db.Text)
    campaign_email = db.Column(db.Text)


    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("person", lazy="subquery"),
        foreign_keys="Product.orcid_id"
    )

    def __init__(self, **kwargs):
        shortuuid.set_alphabet('abcdefghijklmnopqrstuvwxyz1234567890')
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        super(Person, self).__init__(**kwargs)


    def calculate_profile_summary_numbers(self):
        pass

    def make_badges(self):
        pass

    # doesn't throw errors; sets error column if error
    def refresh(self, high_priority=False):

        print u"refreshing {}".format(self.orcid_id)
        self.error = None

        # call orcid api.  includes error handling.
        try:       
            self.set_attributes_and_works_from_orcid()
        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "timeout orcid data error"
            print self.error
        except Exception:
            logging.exception("orcid data error")
            self.error = "orcid data error"

        # now call altmetric.com api. includes error handling and rate limiting.
        # blocks, so might sleep for a long time if waiting out API rate limiting
        # error handling done inside called function so it can be specific to the work
        self.set_data_from_altmetric(high_priority)

        self.calculate_profile_summary_numbers()
        self.make_badges()

        self.updated = datetime.datetime.utcnow().isoformat()

        print u"{orcid_id}: updated metrics for all {num} products\n".format(
            orcid_id=self.orcid_id, 
            num=len(self.products))

        if self.error:
            print u"ERROR refreshing profile {id}: {msg}".format(
                id=self.id, 
                msg=self.error)



    def add_product(self, product_to_add):
        if product_to_add.doi in [p.doi for p in self.products]:
            return False
        else:
            self.products.append(product_to_add)
            return True


    def set_attributes_and_works_from_orcid(self):
        # look up profile in orcid and set/overwrite our attributes
        orcid_data = make_and_populate_orcid_profile(self.orcid_id)

        self.given_names_orcid = orcid_data.given_names
        self.family_name_orcid = orcid_data.family_name
        self.api_raw = json.dumps(orcid_data.api_raw_profile)

        # now walk through all the orcid works and save the most recent ones in our db
        all_products = []
        for work in orcid_data.works:
            try:
                # add product if DOI not all ready there
                # dedup the DOIs here so we get 100 deduped ones below
                my_product = make_product(work)
                if my_product.doi not in [p.doi for p in all_products]:
                    all_products.append(my_product)
            except NoDoiException:
                # just ignore this work, it's not a product for our purposes.
                pass

        # set number of products to be the number of deduped DOIs, before taking most recent
        self.num_products = len(all_products)

        # sort all products by most recent year first
        all_products.sort(key=operator.attrgetter('year_int'), reverse=True)

        # then keep only most recent N DOIs
        for my_product in all_products[:100]:
            self.add_product(my_product)


    def set_data_from_altmetric(self, high_priority=False):
        threads = []

        # start a thread for each work
        # threads may block for a while sleeping if run out of API calls
        for work in self.products:
            process = threading.Thread(target=work.set_altmetric_api_raw, args=[high_priority])
            process.start()
            threads.append(process)

        # wait till all work is done
        for process in threads:
            process.join()

        # now go see if any of them had errors
        # need to do it this way because can't catch thread failures; have to check
        # object afterwards instead to see if they logged failures
        for work in self.products:
            if work.error:
                # don't print out doi here because that could cause another bug
                print u"setting person error; {} for product {}".format(work.error, work.id)
                self.error = work.error


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
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=999),
            'picture': self.picture
        }
        token = jwt.encode(payload, os.getenv("JWT_KEY"))
        return token.decode('unicode_escape')



    def __repr__(self):
        return u'<Person ({id}, {orcid_id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            orcid_id=self.orcid_id,
            given_names=self.given_names_orcid,
            family_name=self.family_name_orcid
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
