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
from util import date_as_iso_utc
from time import time
from collections import defaultdict


def delete_person(orcid_id):
    Person.query.filter_by(orcid_id=orcid_id).delete()
    badge.Badge.query.filter_by(orcid_id=orcid_id).delete()
    product.Product.query.filter_by(orcid_id=orcid_id).delete()
    db.session.commit()

def set_person_email(orcid_id, email, high_priority=False):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    my_person.email = email
    my_person.refresh(high_priority=high_priority)
    db.session.merge(my_person)
    db.session.commit()


def make_person(orcid_id, high_priority=False):
    my_person = Person(orcid_id=orcid_id)
    db.session.add(my_person)
    print u"\nmade new person for {}".format(orcid_id)
    my_person.refresh(high_priority=high_priority)
    db.session.commit()
    return my_person

def pull_from_orcid(orcid_id, high_priority=False):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    my_person.refresh(high_priority=high_priority)
    db.session.merge(my_person)
    db.session.commit()


# @todo refactor this to use the above functions
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

    belt = db.Column(db.Text)
    t_index = db.Column(db.Integer)
    impressions = db.Column(db.Integer)
    num_products = db.Column(db.Integer)
    num_sources = db.Column(db.Integer)

    post_counts = db.Column(MutableDict.as_mutable(JSONB))
    num_with_metrics = db.Column(MutableDict.as_mutable(JSONB))

    altmetric_score = db.Column(db.Float)

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    error = db.Column(db.Text)

    campaign = db.Column(db.Text)
    email = db.Column(db.Text)
    depsy_id = db.Column(db.Text)
    depsy_percentile = db.Column(db.Float)
    twitter = db.Column(db.Text)


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

    def set_belt(self):
        # 0 is one third of people less than 25
        # < 3 is 44% of people between 1 and 25, and 67% of people between 0 and 25
        # < 5 is 54% of people between 1 and 25, and 73% of people between 0 and 25

        # select url, altmetric_score, num_sources, num_nonzero_products  from (
        # select 'http://tng.impactstory.org/u/' || orcid_id as url,
        # 	campaign,
        # 	altmetric_score::int,
        # 	num_sources,
        # 	(select count(id) from product pro where per.orcid_id = pro.orcid_id and altmetric_score > 0) as num_nonzero_products
        # from person per
        # order by altmetric_score asc) sub
        # where  ((campaign = 'impactstory_nos') or (campaign = 'impactstory_subscribers'))
        # and altmetric_score > 25
        # and altmetric_score <= 75
        # and num_sources >= 3

        if (self.altmetric_score >= 250) and (self.num_sources >= 5) and (self.num_non_zero_products >= 5):
            self.belt = "1_black"
        elif (self.altmetric_score >= 75) and (self.num_sources >= 5) and (self.num_non_zero_products >= 5):
            self.belt = "2_brown"
        elif (self.altmetric_score >= 25) and (self.num_sources >= 3):
            self.belt = "3_orange"
        elif (self.altmetric_score >= 3):
            self.belt = "4_yellow"
        else:
            self.belt = "5_white"
        return self.belt


    # doesn't throw errors; sets error column if error
    def refresh(self, high_priority=False):

        print u"** refreshing {}".format(self.orcid_id)
        self.error = None
        start_time = time()
        try:
            print u"* calling set_attributes_and_works_from_orcid"
            self.set_attributes_and_works_from_orcid()

            # now call altmetric.com api. includes error handling and rate limiting.
            # blocks, so might sleep for a long time if waiting out API rate limiting
            # also has error handling done inside called function so it can be specific to the work

            print u"* calling set_data_from_altmetric_for_all_products"
            self.set_data_from_altmetric_for_all_products(high_priority)

            print u"* calling calculate"
            self.calculate()

            print u"* calling assign_badges"
            self.assign_badges()

            print u"took {sec}s to refresh all {num} products for {orcid_id}".format(
                orcid_id=self.orcid_id,
                num=len(self.products),
                sec=elapsed(start_time)
            )

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "requests timeout error"
        except Exception:
            logging.exception("refresh error")
            self.error = "refresh error"
        finally:
            self.updated = datetime.datetime.utcnow().isoformat()
            if self.error:
                print u"ERROR refreshing person {}: {}".format(self.id, self.error)

    def add_product(self, product_to_add):
        if product_to_add.doi in [p.doi for p in self.products]:
            return False
        else:
            self.products.append(product_to_add)
            return True

    def calculate(self):
        self.set_post_counts() # do this first
        self.set_altmetric_score()
        self.set_t_index()
        self.set_depsy()
        self.set_impressions()
        self.set_num_with_metrics()
        self.set_num_sources()
        self.set_belt()  # do this last, depends on other things


    def set_depsy(self):
        if self.email:
            headers = {'Accept': 'application/json'}
            # example http://depsy.org/api/search/person?email=ethan@weecology.org
            url = "http://depsy.org/api/search/person?email={}".format(self.email)
            # might throw requests.Timeout
            r = requests.get(url, headers=headers, timeout=10)
            response_dict = r.json()
            if response_dict["count"] > 0:
                self.depsy_id = response_dict["list"][0]["id"]
                self.depsy_percentile = response_dict["list"][0]["impact_percentile"]
                print u"got a depsy id for {}: {}".format(self.id, self.depsy_id)

    def set_attributes_and_works_from_orcid(self):
        # look up profile in orcid and set/overwrite our attributes
        orcid_data = make_and_populate_orcid_profile(self.orcid_id)

        self.given_names = orcid_data.given_names
        self.family_name = orcid_data.family_name
        if orcid_data.best_affiliation:
            self.affiliation_name = orcid_data.best_affiliation["name"]
            self.affiliation_role_title = orcid_data.best_affiliation["role_title"]

        if orcid_data.researcher_urls:
            for url_dict in orcid_data.researcher_urls:
                url = url_dict["url"]["value"]
                if "twitter.com" in url:
                    #regex from http://stackoverflow.com/questions/4424179/how-to-validate-a-twitter-username-using-regex
                    match = re.findall("twitter.com/([A-Za-z0-9_]{1,15}$)", url)
                    if match:
                        self.twitter = match[0]
                        print u"found twitter screen_name! {}".format(self.twitter)
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

        # print u"t-index={t_index} based on {tweeted_count} tweeted products ({total} total)".format(
        #     t_index=self.t_index,
        #     tweeted_count=len([x for x in tweet_counts if x]),
        #     total=len(my_products)
        # )

    @property
    def picture(self):
        if self.email:
            email_hash = hashlib.md5(self.email).hexdigest()
        else:
            email_hash = ""  #will return blank face
        url = u"https://www.gravatar.com/avatar/{}?s=110&d=mm".format(email_hash)
        return url


    @property
    def wikipedia_urls(self):
        articles = set()
        for my_product in self.products:
            if my_product.post_counts_by_source("wikipedia"):
                articles.update(my_product.wikipedia_urls)
        return articles

    @property
    def distinct_fans_count(self):
        fans = set()
        for my_product in self.products:
            for fan_name in my_product.twitter_posters_with_followers:
                fans.add(fan_name)
        return len(fans)

    @property
    def countries(self):
        countries = set()
        for my_product in self.products:
            for my_country in my_product.countries:
                if my_country:
                    countries.add(my_country)
        return sorted(countries)



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
            # print u"set event_dates for {} {}".format(self.id, source)

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

    def post_counts_by_source(self, source_name):
        if source_name in self.post_counts:
            return self.post_counts[source_name]
        return 0

    def set_post_counts(self):
        self.post_counts = {}

        for p in self.products:
            for metric, count in p.post_counts.iteritems():
                try:
                    self.post_counts[metric] += int(count)
                except KeyError:
                    self.post_counts[metric] = int(count)

        # print u"setting post_counts", self.post_counts

    def set_num_sources(self):
        self.num_sources = len(self.post_counts.keys())
        # print u"set num_sources=", self.num_sources

    def set_num_with_metrics(self):
        if self.num_with_metrics is None:
            self.num_with_metrics = {}

        for p in self.products:
            for metric, count in p.post_counts.iteritems():
                try:
                    self.num_with_metrics[metric] += 1
                except KeyError:
                    self.num_with_metrics[metric] = 1

        # print "setting num_with_metrics", self.num_with_metrics


    def get_token(self):
        payload = {
            'sub': self.orcid_id,
            'given_names': self.given_names,
            'family_name': self.family_name,
            'created': date_as_iso_utc(self.created),
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
        for badge_assigner_class in badge_defs.all_badge_assigners():
            badge_assigner = badge_assigner_class()
            candidate_badge = badge_assigner.get_badge_or_None(self)
            already_assigned_badge = self.get_badge(badge_assigner.name)

            if candidate_badge:
                if already_assigned_badge:
                    # print u"{} already had badge {}, UPDATING products and support".format(self.id, candidate_badge)
                    already_assigned_badge.products = candidate_badge.products
                    already_assigned_badge.support = candidate_badge.support
                else:
                    print u"{} first time got badge {}".format(self.id, candidate_badge)
                    self.badges.append(candidate_badge)
            else:
                # print u"nope, {} doesn't get badge {}".format(self.id, badge_assigner.name)
                if already_assigned_badge:
                    print u"{} doesn't get badge {}, but had it before, so removing".format(self.id, badge_assigner.name)
                    badge.Badge.query.filter_by(id=already_assigned_badge.id).delete()


    @property
    def full_name(self):
        return u"{} {}".format(self.given_names, self.family_name)

    def set_impressions(self):
        self.impressions = sum([p.impressions for p in self.products])


    @property
    def num_non_zero_products(self):
        return len(self.non_zero_products)


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
            "_id": self.id,  # do this too, so it is on top
            "_full_name": self.full_name,
            "id": self.id,
            "orcid_id": self.orcid_id,
            "given_names": self.given_names,
            "family_name": self.family_name,
            "created": date_as_iso_utc(self.created),
            "updated": date_as_iso_utc(self.updated),
            "picture": self.picture,
            "affiliation_name": self.affiliation_name,
            "affiliation_role_title": self.affiliation_role_title,
            "twitter": self.twitter,
            "depsy_id": self.depsy_id,
            "depsy_percentile": self.depsy_percentile,
            "altmetric_score": self.altmetric_score,
            "belt": self.belt.split("_")[1],
            "t_index": self.t_index,
            "impressions": self.impressions,
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
