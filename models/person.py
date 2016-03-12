from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError

from app import db

from models import product  # needed for sqla i think
from models import badge  # needed for sqla i think
from models.orcid import OrcidProfile
from models.product import make_product
from models.product import NoDoiException
from models.orcid import make_and_populate_orcid_profile
from models.source import sources_metadata
from models.source import Source
from models import badge_defs

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
import hashlib
from util import elapsed
from time import time
from collections import defaultdict



def make_person_from_google(person_dict):
    print "\n\nmaking new person with person_dict: ", person_dict, "\n\n"
    new_person = Person(
        email=person_dict["email"],
        given_name=person_dict["given_name"],
        family_name=person_dict["family_name"],
        oauth_source='google',
        oauth_api_raw=person_dict
    )

    db.session.add(new_person)
    db.session.commit()

    return new_person





def add_or_overwrite_person_from_orcid_id(orcid_id,
                                          high_priority=False):

    # if one already there, use it and overwrite.  else make a new one.
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    if my_person:
        db.session.merge(my_person)
        print u"\nusing already made person for {}".format(orcid_id)
    else:
        # make a person with this orcid_id
        my_person = Person(orcid_id=orcid_id)
        db.session.add(my_person)
        print u"\nmade new person for {}".format(orcid_id)

    my_person.refresh(high_priority=high_priority)

    # now write to the db
    db.session.commit()
    return my_person


class Person(db.Model):
    id = db.Column(db.Text, primary_key=True)
    orcid_id = db.Column(db.Text, unique=True)

    oauth_source = db.Column(db.Text)
    oauth_api_raw = db.Column(JSONB)

    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    affiliation_name = db.Column(db.Text)
    affiliation_role_title = db.Column(db.Text)
    api_raw = db.Column(db.Text)

    t_index = db.Column(db.Integer)
    num_products = db.Column(db.Integer)

    post_counts = db.Column(MutableDict.as_mutable(JSONB))
    num_with_metrics = db.Column(MutableDict.as_mutable(JSONB))
    num_sources = db.Column(db.Integer)

    altmetric_score = db.Column(db.Float)

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    error = db.Column(db.Text)

    campaign = db.Column(db.Text)
    email = db.Column(db.Text)


    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("person", lazy="subquery"),
        foreign_keys="Product.orcid_id"
    )

    badges = db.relationship(
        'Badge',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("person", lazy="subquery"),
        foreign_keys="Badge.orcid_id"
    )


    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        super(Person, self).__init__(**kwargs)

    @property
    def belt(self):
        # 0 is one third of people less than 25
        # < 3 is 44% of people between 1 and 25, and 67% of people between 0 and 25
        # < 5 is 54% of people between 1 and 25, and 73% of people between 0 and 25

        # ugly sql to estimate breakpoints
        # select round(altmetric_score), sum(count(*)) OVER (ORDER BY round(altmetric_score)), (sum(count(*)) OVER (ORDER BY round(altmetric_score))) / 600
        # from temp_2015_with_urls_low_score
        # where altmetric_score > 0
        # group by round(altmetric_score)
        # order by round(altmetric_score) asc

        if self.altmetric_score < 3:
            return "white"
        if self.altmetric_score < 25:
            return "yellow"
        if self.altmetric_score < 500:
            return "orange"
        if self.altmetric_score < 1000:
            return "brown"
        return "black"


    # doesn't throw errors; sets error column if error
    def refresh(self, high_priority=False):

        print u"refreshing {}".format(self.orcid_id)
        self.error = None
        start_time = time()
        try:
            print u"calling set_attributes_and_works_from_orcid"
            self.set_attributes_and_works_from_orcid()

            # now call altmetric.com api. includes error handling and rate limiting.
            # blocks, so might sleep for a long time if waiting out API rate limiting
            # also has error handling done inside called function so it can be specific to the work
            print u"calling set_data_from_altmetric_for_all_products"
            self.set_data_from_altmetric_for_all_products(high_priority)

            print u"calling calculate_profile_summary_numbers"
            self.calculate_profile_summary_numbers()
            print u"calling assign_badges"
            self.assign_badges()

            print u"updated metrics for all {num} products for {orcid_id} in {sec}s".format(
                orcid_id=self.orcid_id,
                num=len(self.products),
                sec=elapsed(start_time)
            )

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "timeout error"
            print self.error
        except Exception:
            logging.exception("refresh error")
            self.error = "refresh error"
        finally:
            self.updated = datetime.datetime.utcnow().isoformat()
            if self.error:
                print u"ERROR refreshing profile {}: {}".format(self.id, self.error)

    def add_product(self, product_to_add):
        if product_to_add.doi in [p.doi for p in self.products]:
            return False
        else:
            self.products.append(product_to_add)
            return True

    def calculate_profile_summary_numbers(self):
        self.set_altmetric_score()
        self.set_t_index()
        self.set_post_counts()
        self.set_num_sources()
        self.set_num_with_metrics()

    def set_attributes_and_works_from_orcid(self):
        # look up profile in orcid and set/overwrite our attributes
        orcid_data = make_and_populate_orcid_profile(self.orcid_id)

        self.given_names = orcid_data.given_names
        self.family_name = orcid_data.family_name
        if orcid_data.best_affiliation:
            self.affiliation_name = orcid_data.best_affiliation["name"]
            self.affiliation_role_title = orcid_data.best_affiliation["role_title"]
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


    def set_data_from_altmetric_for_all_products(self, high_priority=False):
        threads = []

        # start a thread for each work
        # threads may block for a while sleeping if run out of API calls
        for work in self.products:
            process = threading.Thread(target=work.set_data_from_altmetric, args=[high_priority])
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


    def set_t_index(self):
        my_products = self.products

        tweet_counts = []
        for p in my_products:
            try:
                int(tweet_counts.append(p.post_counts["twitter"]))
            except (KeyError, TypeError):
                tweet_counts.append(0)

        self.t_index = h_index(tweet_counts)

        print u"t-index={t_index} based on {tweeted_count} tweeted products ({total} total)".format(
            t_index=self.t_index,
            tweeted_count=len([x for x in tweet_counts if x]),
            total=len(my_products)
        )

    @property
    def picture(self):
        if self.email:
            email_hash = hashlib.md5(self.email).hexdigest()
        else:
            email_hash = ""  #will return blank face
        url = u"https://www.gravatar.com/avatar/{}?s=110&d=mm".format(email_hash)
        return url


    @property
    def sources(self):
        sources = []
        for source_name in sources_metadata:
            source = Source(source_name, self.products)
            if source.posts_count > 0:
                sources.append(source)
        return sources

    @property
    def all_event_days_ago(self):
        return self.set_event_dates()

    def set_event_dates(self):
        self.event_dates = {}

        for product in self.products:
            if product.event_days_ago:
                for source, dates_list in product.event_days_ago.iteritems():
                    if not source in self.event_dates:
                        self.event_dates[source] = []
                    self.event_dates[source] += dates_list

        # now sort them all
        for source in self.event_dates:
            self.event_dates[source].sort(reverse=False)
            print u"set event_dates for {} {}".format(self.id, source)

        return self.event_dates

    @property
    def event_days_histogram(self):
        if not self.all_event_days_ago:
            return {}

        max_days_ago = max([self.all_event_days_ago[source][-1] for source in self.all_event_days_ago])
        resp = {}

        for (source, days_ago_list) in self.all_event_days_ago.iteritems():
            resp[source] = []
            running_total = 0
            for accumulating_day in reversed(range(max_days_ago)):
                running_total += len([d for d in days_ago_list if d==accumulating_day])
                resp[source].append(running_total)
        return resp

    def set_altmetric_score(self):
        self.altmetric_score = 0
        for p in self.products:
            if p.altmetric_score:
                self.altmetric_score += p.altmetric_score
        print u"total altmetric score: {}".format(self.altmetric_score)


    def set_post_counts(self):
        if self.post_counts is None:
            self.post_counts = {}

        for p in self.products:
            for metric, count in p.post_counts.iteritems():
                try:
                    self.post_counts[metric] += int(count)
                except KeyError:
                    self.post_counts[metric] = int(count)

        print "setting post_counts", self.post_counts

    def set_num_sources(self):
        if self.post_counts is None:
            self.post_counts = {}

        self.num_sources = len(self.post_counts.keys())
        print u"set num_sources=", self.num_sources

    def set_num_with_metrics(self):
        if self.num_with_metrics is None:
            self.num_with_metrics = {}

        for p in self.products:
            for metric, count in p.post_counts.iteritems():
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
        }
        token = jwt.encode(payload, os.getenv("JWT_KEY"))
        return token.decode('unicode_escape')

    def get_badge(self, badge_name):
        for badge in self.badges:
            if badge.name == badge_name:
                return badge
        return None

    def assign_badges(self):
        for badge_def in badge_defs.all_badge_defs:
            print u"trying badge {}".format(badge_def["name"])
            new_badge = get_badge_or_None(badge_def, self)
            if new_badge:
                already_assigned_badge = self.get_badge(new_badge.name)
                if already_assigned_badge:
                    print u"already had badge, updating products for {}".format(new_badge)
                    already_assigned_badge.products = new_badge.products
                else:
                    print u"added badge {}".format(badge)
                    self.badges.append(new_badge)
            else:
                print u"nope, doesn't get badge {}".format(badge_def["name"])

    @property
    def non_zero_products(self):
        resp = []
        for my_product in self.products:
            if my_product.altmetric_score > 0:
                resp.append(my_product)
        return resp



    def __repr__(self):
        return u'<Person ({id}, {orcid_id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            orcid_id=self.orcid_id,
            given_names=self.given_names,
            family_name=self.family_name
        )


    def to_dict(self):
        return {
            "id": self.id,
            "orcid_id": self.orcid_id,
            "given_names": self.given_names,
            "family_name": self.family_name,
            "picture": self.picture,
            "affiliation_name": self.affiliation_name,
            "affiliation_role_title": self.affiliation_role_title,
            "twitter": "ethanwhite",  #placeholder
            "depsy": "332509", #placeholder
            "altmetric_score": self.altmetric_score,
            "belt": self.belt,
            "t_index": self.t_index,
            "impressions": self.altmetric_score * 100,  #placeholder
            "sources": [s.to_dict() for s in self.sources],
            "badges": [b.to_dict() for b in self.badges],
            "products": [p.to_dict() for p in self.non_zero_products]
            # "all_event_days_ago": json.dumps(self.all_event_days_ago),
            # "event_days_histogram": json.dumps(self.event_days_histogram),
        }



def h_index(citations):
    # from http://www.rainatian.com/2015/09/05/leetcode-python-h-index/

    citations.sort(reverse=True)

    i=0
    while (i<len(citations) and i+1 <= citations[i]):
        i += 1

    return i
