from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import deferred
from sqlalchemy import orm
from sqlalchemy import text
from sqlalchemy import func

from app import db

from models import product  # needed for sqla i think
from models import badge  # needed for sqla i think
from models.product import make_product
from models.orcid import OrcidProfile
from models.orcid import clean_orcid
from models.orcid import NoOrcidException
from models.orcid import OrcidDoesNotExist
from models.orcid import make_and_populate_orcid_profile
from models.source import sources_metadata
from models.source import Source
from models.country import country_info
from models.top_news import top_news_titles
from models.oa import is_open_product_id
from util import elapsed
from util import chunks
from util import date_as_iso_utc
from util import days_ago
from util import safe_commit
from util import calculate_percentile
from util import NoDoiException
from util import normalize
from util import replace_punctuation

from time import time
from time import sleep
from copy import deepcopy
import jwt
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
import math
from nameparser import HumanName
from collections import defaultdict
from requests_oauthlib import OAuth1Session



def delete_person(orcid_id):

    # also need delete all the badges, products
    product.Product.query.filter_by(orcid_id=orcid_id).delete()
    badge.Badge.query.filter_by(orcid_id=orcid_id).delete()

    # and now delete the person.  have to do this after deleting the stuff above.
    Person.query.filter_by(orcid_id=orcid_id).delete()

    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(orcid_id)

def set_person_email(orcid_id, email, high_priority=False):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    my_person.email = email
    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(orcid_id)

def set_person_claimed_at(my_person):
    my_person.claimed_at = datetime.datetime.utcnow().isoformat()
    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.orcid_id)

def make_person(dirty_orcid_id, high_priority=False):
    orcid_id = clean_orcid(dirty_orcid_id)
    my_person = Person(orcid_id=orcid_id)
    db.session.add(my_person)
    print u"\nmade new person for {}".format(orcid_id)
    my_person.refresh(refsets, high_priority=high_priority)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(orcid_id)

    if my_person.invalid_orcid:
        raise OrcidDoesNotExist

    return my_person

def refresh_profile(orcid_id, high_priority=False):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    my_person.refresh(refsets, high_priority=high_priority)
    db.session.merge(my_person)
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(orcid_id)
    return my_person

def link_twitter(orcid_id, twitter_creds):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    my_person.twitter_creds = twitter_creds


    oauth = OAuth1Session(
        os.getenv('TWITTER_CONSUMER_KEY'),
        client_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
        resource_owner_key=twitter_creds["oauth_token"],
        resource_owner_secret=twitter_creds["oauth_token_secret"]
    )
    url = "https://api.twitter.com/1.1/account/verify_credentials.json?include_email=true"

    r = oauth.get(url)
    full_twitter_profile = r.json()
    # print "we got this back from Twitter!", full_twitter_profile

    full_twitter_profile.update(twitter_creds)
    my_person.twitter_creds = full_twitter_profile
    if my_person.email is None:
        my_person.email = full_twitter_profile["email"]

    my_person.twitter = full_twitter_profile["screen_name"]

    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(orcid_id)
    return my_person






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

    my_person.refresh(refsets, high_priority=high_priority)

    # now write to the db
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on {}".format(my_person.orcid_id)
    return my_person



class Person(db.Model):
    id = db.Column(db.Text, primary_key=True)
    orcid_id = db.Column(db.Text, unique=True)

    first_name = db.Column(db.Text)
    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    affiliation_name = db.Column(db.Text)
    affiliation_role_title = db.Column(db.Text)

    orcid_api_raw_json = deferred(db.Column(JSONB))
    invalid_orcid = db.Column(db.Boolean)

    num_products = db.Column(db.Integer)
    num_posts = db.Column(db.Integer)

    post_counts = db.Column(MutableDict.as_mutable(JSONB))
    coauthors = db.Column(MutableDict.as_mutable(JSONB))

    score = db.Column(db.Float)
    buzz = db.Column(db.Float)
    influence = db.Column(db.Float)
    consistency = db.Column(db.Float)
    geo = db.Column(db.Float)
    openness = db.Column(db.Float)

    score_perc = db.Column(db.Float)
    buzz_perc = db.Column(db.Float)
    influence_perc = db.Column(db.Float)
    consistency_perc = db.Column(db.Float)
    geo_perc = db.Column(db.Float)
    openness_perc = db.Column(db.Float)

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)
    claimed_at = db.Column(db.DateTime)

    weekly_event_count = db.Column(db.Float)
    monthly_event_count = db.Column(db.Float)
    tweeted_quickly = db.Column(db.Boolean)

    error = db.Column(db.Text)

    campaign = db.Column(db.Text)
    email = db.Column(db.Text)
    depsy_id = db.Column(db.Text)
    depsy_percentile = db.Column(db.Float)
    twitter = db.Column(db.Text)
    twitter_creds = db.Column(MutableDict.as_mutable(JSONB))


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


    def __init__(self, orcid_id):
        self.id = orcid_id
        self.orcid_id = orcid_id
        self.invalid_orcid = False
        self.created = datetime.datetime.utcnow().isoformat()


    # doesn't have error handling; called by refresh when you want it to be robust
    def call_apis(self, high_priority=False, overwrite_orcid=True, overwrite_altmetric=True):
        print u"** calling set_api_raw_from_orcid"
        if overwrite_orcid or not self.orcid_api_raw_json:
            self.set_api_raw_from_orcid()
        else:
            print u"not calling orcid because no overwrite"

        # parse orcid so we now what to gather
        self.set_from_orcid()

        # never bother overwriting crossref, so isn't even an option
        products_without_crossref = [p for p in self.products if not p.crossref_api_raw]

        if products_without_crossref:
            print u"** calling set_data_for_all_products for crossref doi lookup"
            # do this first, so have doi for everything else
            self.set_data_for_all_products("set_doi_from_crossref_biblio_lookup", high_priority)

            print u"** calling set_data_for_all_products for crossref"
            self.set_data_for_all_products("set_data_from_crossref", high_priority)
        else:
            print u"** all products have crossref data, so not calling crossref"

        products_without_altmetric = [p for p in self.products if not p.altmetric_api_raw]
        if overwrite_altmetric or products_without_altmetric:
            print u"** calling set_data_for_all_products for altmetric"
            self.set_data_for_all_products("set_data_from_altmetric", high_priority)
        else:
            print u"** all products have altmetric data and no overwrite, so not calling altmetric"


    # doesn't have error handling; called by refresh when you want it to be robust
    def refresh_from_db(self, my_refsets):
        print u"* refresh_from_db {}".format(self.orcid_id)
        self.error = None
        start_time = time()
        try:
            print u"** calling call_apis with overwrites false"
            self.call_apis(my_refsets, overwrite_orcid=False, overwrite_altmetric=False)

            print u"** calling calculate"
            self.calculate(my_refsets)
        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "requests timeout"
        except OrcidDoesNotExist:
            self.invalid_orcid = True
            self.error = "invalid orcid"
        except Exception:
            logging.exception("refresh error")
            self.error = "refresh error"
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()
        finally:
            self.updated = datetime.datetime.utcnow().isoformat()
            if self.error:
                print u"ERROR refreshing person {} {}: {}".format(self.id, self.orcid_id, self.error)


    # doesn't throw errors; sets error column if error
    def refresh(self, my_refsets, high_priority=False):

        print u"* refreshing {}".format(self.orcid_id)
        self.error = None
        start_time = time()
        try:
            print u"** calling call_apis"
            self.call_apis(high_priority=high_priority)

            print u"** calling calculate"
            self.calculate(my_refsets)

            print u"** finished refreshing all {num} products for {orcid_id} in {sec}s".format(
                orcid_id=self.orcid_id,
                num=len(self.all_products),
                sec=elapsed(start_time)
            )

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "requests timeout"
        except OrcidDoesNotExist:
            self.invalid_orcid = True
            self.error = "invalid orcid"
        except Exception:
            logging.exception("refresh error")
            self.error = "refresh error"
            print u"in generic exception handler, so rolling back in case it is needed"
            db.session.rollback()
        finally:
            self.updated = datetime.datetime.utcnow().isoformat()
            if self.error:
                print u"ERROR refreshing person {} {}: {}".format(self.id, self.orcid_id, self.error)


    def set_hybrid(self, high_priority=False):
        self.set_data_for_all_products("set_data_from_hybrid", high_priority)

    def set_products(self, products_to_add):
        updated_products = []

        for product_to_add in products_to_add:
            needs_to_be_added = True
            for my_existing_product in self.products:
                if my_existing_product.orcid_put_code == product_to_add.orcid_put_code:
                    # update the product biblio from the most recent orcid api response
                    my_existing_product.orcid_api_raw_json = product_to_add.orcid_api_raw_json
                    my_existing_product.set_biblio_from_orcid()
                    updated_products.append(my_existing_product)
                    needs_to_be_added = False
            if needs_to_be_added:
                updated_products.append(product_to_add)
        self.products = updated_products



    def calculate(self, my_refsets):
        # things with api calls in them, or things needed to make those calls
        start_time = time()
        self.set_publisher()
        self.set_is_open()
        self.set_depsy()
        print u"finished api calling part of {method_name} on {num} products in {sec}s".format(
            method_name="calculate".upper(),
            num = len(self.products),
            sec = elapsed(start_time, 2)
        )

        # everything else
        start_time = time()
        self.set_post_counts() # do this first
        self.set_num_posts()
        self.set_subscores()
        if my_refsets:
            self.set_subscore_percentiles(my_refsets)
        self.set_event_counts()
        self.set_coauthors()  # do this last, uses scores
        print u"finished calculating part of {method_name} on {num} products in {sec}s".format(
            method_name="calculate".upper(),
            num = len(self.products),
            sec = elapsed(start_time, 2)
        )

        start_time = time()
        self.assign_badges()
        if my_refsets:
            print u"** calling set_badge_percentiles"
            self.set_badge_percentiles(my_refsets)
        print u"finished badges part of {method_name} on {num} products in {sec}s".format(
            method_name="calculate".upper(),
            num = len(self.products),
            sec = elapsed(start_time, 2)
        )


    def set_is_open_temp(self):
        for p in self.all_products:
            if not p.is_open and is_open_product_id(p):
                # print u"is open! {}".format(p.url)
                p.is_open = True
                p.open_url = p.url
                p.open_urls = {"urls": [p.open_url]}

    def set_is_open(self):

        start_time = time()

        for p in self.all_products:
            p.is_open = False
            p.open_url = None
            p.open_urls = {"urls": []}

        # may be more than one product for a given title, so is a dict of lists
        titles = []
        titles_to_products = defaultdict(list)
        for p in self.all_products:
            if is_open_product_id(p):
                # print u"is open! {}".format(p.url)
                p.is_open = True
                p.open_url = p.url
                p.open_urls = {"urls": [p.open_url]}

                # is already open, so don't need to look it up
                continue

        print u"finished local step of set_is_open in {sec}s".format(
            sec = elapsed(start_time, 2)
        )
        # start_time = time()

        # uncomment this when we want to use base again
        #     if p.title:
        #         title = p.title
        #         titles_to_products[normalize(title)].append(p)
        #
        #         title = title.lower()
        #         # can't just replace all punctuation because ' replaced with ? gets no hits
        #         title = title.replace('"', "?")
        #         title = title.replace('#', "?")
        #         title = title.replace('=', "?")
        #         title = title.replace('&', "?")
        #         title = title.replace('%', "?")
        #
        #         # only bother looking up titles that are at least 3 words long
        #         title_words = title.split()
        #         if len(title_words) >= 3:
        #             # only look up the first 12 words
        #             title_to_query = u" ".join(title_words[0:12])
        #             titles.append(title_to_query)
        #
        # # for title_group in chunks(titles, 1):
        # for title_group in chunks(titles, 100):
        #     titles_string = u"%20OR%20".join([u'%22{}%22'.format(title) for title in title_group])
        #
        #     url_template = u"https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi?func=PerformSearch&query=(dcoa:1%20OR%20dcoa:2)%20AND%20dctitle:({titles_string})&fields=dctitle,dccreator,dcyear,dcrights,dcprovider,dcidentifier,dcoa,dclink&hits=100000&format=json"
        #     url = url_template.format(titles_string=titles_string)
        #     # print u"calling {}".format(url)
        #
        #     start_time = time()
        #     proxies = {"https": "http://quotaguard5381:ccbae172bbeb@us-east-static-01.quotaguard.com:9293"}
        #     try:
        #         r = requests.get(url, proxies=proxies, timeout=4)
        #         print u"** querying with {} titles took {}s".format(len(title_group), elapsed(start_time))
        #     except requests.exceptions.ConnectionError:
        #         for p in self.all_products:
        #             p.is_open = None
        #         print u"connection error in set_is_open on {}, skipping.".format(self.orcid_id)
        #         return
        #     except requests.Timeout:
        #         for p in self.all_products:
        #             p.is_open = None
        #         print u"timeout error in set_is_open on {} {}, skipping.".format(self.orcid_id, self.id)
        #         return
        #
        #     if r.status_code != 200:
        #         print u"problem!  status_code={}".format(r.status_code)
        #     else:
        #         try:
        #             data = r.json()["response"]
        #             # print "number found:", data["numFound"]
        #             print "num docs in this response", len(data["docs"])
        #             for doc in data["docs"]:
        #                 try:
        #                     matching_products = titles_to_products[normalize(doc["dctitle"])]
        #                     for p in matching_products:
        #                         p.is_open = True
        #                         p.open_urls["urls"] += doc["dcidentifier"]
        #                         if not p.base_dcoa or p.base_dcoa == "2":
        #                             p.base_dcoa = str(doc["dcoa"])
        #                             p.base_dcprovider = doc["dcprovider"]
        #
        #                         # use a doi whenever we have it
        #                         for identifier in doc["dcidentifier"]:
        #                             if "doi.org" in identifier or not p.open_url:
        #                                 p.open_url = identifier
        #
        #
        #                 except KeyError:
        #                     # print u"no hit with title {}".format(doc["dctitle"])
        #                     # print u"normalized: {}".format(normalize(doc["dctitle"]))
        #                     pass
        #         except ValueError:  # includes simplejson.decoder.JSONDecodeError
        #             logging.exception("Value Error")
        #             for p in self.all_products:
        #                 p.is_open = None
        #             print u'***Error: decoding JSON has failed on {} {}'.format(self.orcid_id, url)

        # print u"finished base step of set_is_open in {sec}s".format(
        #     sec = elapsed(start_time, 2)
        # )


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

    def set_first_name(self):
        try:
            self.first_name = HumanName(self.full_name)["first"]
        except KeyError:
            self.first_name = self.given_names
        # print u"set first name {} as first name for {}".format(self.first_name, self.full_name)


    def set_api_raw_from_orcid(self):
        start_time = time()

        # look up profile in orcid
        try:
            orcid_data = make_and_populate_orcid_profile(self.orcid_id)
            self.orcid_api_raw_json = orcid_data.api_raw_profile
        except requests.Timeout:
            self.error = "timeout from requests when getting orcid"

        print u"finished {method_name} in {sec}s".format(
            method_name="set_api_raw_from_orcid".upper(),
            sec = elapsed(start_time, 2)
        )




    def set_from_orcid(self):
        if not self.orcid_api_raw_json:
            print u"no orcid data in db for {}".format(self.orcid_id)
            return

        orcid_data = OrcidProfile(self.orcid_id)
        orcid_data.api_raw_profile = self.orcid_api_raw_json

        self.given_names = orcid_data.given_names
        self.family_name = orcid_data.family_name
        self.set_first_name()  #needs given_names and family_name set already

        if orcid_data.best_affiliation:
            self.affiliation_name = orcid_data.best_affiliation["name"]
            self.affiliation_role_title = orcid_data.best_affiliation["role_title"]

        # now walk through all the orcid works and save the most recent ones in our db
        all_products_by_title = {}
        for work in orcid_data.works:
            my_product = make_product(work)

            if my_product.title:
                normalized_title = normalize(my_product.title)

                # use this product if it is the first one we have with its title
                # or it has a doi and the otherone doesnt
                # or it is more recent
                if ((normalized_title not in all_products_by_title) or \
                        (my_product.doi and not all_products_by_title[normalized_title].doi) or \
                        (my_product.year_int >= all_products_by_title[normalized_title].year_int)):
                    all_products_by_title[normalized_title] = my_product

        all_products = all_products_by_title.values()
        all_products.sort(key=operator.attrgetter('year_int'), reverse=True)

        # keep only most recent products
        all_products = all_products[:100]

        self.set_products(all_products)


    def set_data_for_all_products(self, method_name, high_priority=False):
        start_time = time()
        threads = []

        # start a thread for each work
        # threads may block for a while sleeping if run out of API calls

        for work in self.products:
            method = getattr(work, method_name)
            process = threading.Thread(target=method, args=[high_priority])
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
                # print u"setting person error; {} for product {}".format(work.error, work.id)
                self.error = work.error

        print u"finished {method_name} on {num} products in {sec}s".format(
            method_name=method_name.upper(),
            num = len(self.products),
            sec = elapsed(start_time, 2)
        )



    @property
    def picture(self):
        try:
            url = self.twitter_creds["profile_image_url"].replace("_normal", "")
        except TypeError:
            # no twitter. let's try gravatar

            try:
                email_hash = hashlib.md5(self.email).hexdigest()
            except TypeError:
                # bummer, no email either. that's ok, gravatar will return a blank face for
                # an email they don't have
                email_hash = ""

            url = u"https://www.gravatar.com/avatar/{}?s=110&d=mm".format(email_hash)

        return url


    @property
    def wikipedia_urls(self):
        articles = set()
        for my_product in self.products_with_dois:
            if my_product.post_counts_by_source("wikipedia"):
                articles.update(my_product.wikipedia_urls)
        return articles

    @property
    def distinct_fans_count(self):
        fans = set()
        for my_product in self.products_with_dois:
            for fan_name in my_product.twitter_posters_with_followers:
                fans.add(fan_name)
        return len(fans)

    @property
    def countries(self):
        countries = set()
        for my_product in self.products_with_dois:
            for my_country in my_product.countries:
                if my_country:
                    countries.add(my_country)
        return sorted(countries)


    @property
    def sources(self):
        sources = []
        for source_name in sources_metadata:
            source = Source(source_name, self.products_with_dois)
            if source.posts_count > 0:
                sources.append(source)
        return sources


    # convenience so can have all of these set for one profile
    def set_post_details(self):
        for my_product in self.non_zero_products:
            my_product.set_post_details()


    def set_coauthors(self):
        # comment out the commit.  this means coauthors made during this commit session don't show up on this refresh
        # but doing it because is so much faster
        # safe_commit(db)

        # now go for it
        print u"running coauthors for {}".format(self.orcid_id)
        coauthor_orcid_id_query = u"""select distinct orcid_id
                    from product
                    where doi in
                      (select doi from product where orcid_id='{}')""".format(self.orcid_id)
        rows = db.engine.execute(text(coauthor_orcid_id_query))

        # remove own orcid_id
        orcid_ids = [row[0] for row in rows if row[0] != self.orcid_id]
        if not orcid_ids:
            return

        # don't load products or badges
        coauthors = Person.query.filter(Person.orcid_id.in_(orcid_ids)).options(orm.noload('*')).all()

        resp = {}
        for coauthor in coauthors:
            if coauthor.id != self.id:
                resp[coauthor.orcid_id] = {
                    "name": coauthor.full_name,
                    "id": coauthor.id,
                    "orcid_id": coauthor.orcid_id,
                    "openness_perc": coauthor.display_openness_perc,
                    "engagement_perc": coauthor.display_engagement_perc,
                    "buzz_perc": coauthor.display_buzz_perc
                }
        self.coauthors = resp


    def get_event_dates(self):
        event_dates = []

        for product in self.products_with_dois:
            if product.event_dates:
                for source, dates_list in product.event_dates.iteritems():
                    event_dates += dates_list
        # now sort them all
        event_dates.sort(reverse=False)
        return event_dates

    def set_event_counts(self):
        self.monthly_event_count = 0
        self.weekly_event_count = 0

        event_dates = self.get_event_dates()
        if not event_dates:
            return

        for event_date in event_dates:
            event_days_ago = days_ago(event_date)
            if event_days_ago <= 7:
                self.weekly_event_count += 1
            if event_days_ago <= 30:
                self.monthly_event_count += 1

    # @property
    # def event_days_histogram(self):
    #     if not self.all_event_days_ago:
    #         return {}
    #
    #     max_days_ago = max([self.all_event_days_ago[source][-1] for source in self.all_event_days_ago])
    #     resp = {}
    #
    #     for (source, days_ago_list) in self.all_event_days_ago.iteritems():
    #         resp[source] = []
    #         running_total = 0
    #         for accumulating_day in reversed(range(max_days_ago)):
    #             running_total += len([d for d in days_ago_list if d==accumulating_day])
    #             resp[source].append(running_total)
    #     return resp

    def get_tweeter_names(self, most_recent=None):
        twitter_posts = self.get_twitter_posts(most_recent)
        names = [post["attribution"] for post in twitter_posts if "attribution" in post]
        return names

    def get_twitter_posts(self, most_recent=None):
        twitter_posts = [post for post in self.get_posts() if post["source"]=="twitter"]
        if most_recent:
            twitter_posts = twitter_posts[0:most_recent]
        return twitter_posts

    def get_posts(self):
        posts = []
        for my_product in self.products_with_dois:
            posts += my_product.posts
        return posts

    def get_top_news_posts(self):
        news_posts = []

        for my_product in self.products_with_dois:
            if my_product.post_details and my_product.post_details["list"]:
                for post in my_product.post_details["list"]:
                    if post["source"] == "news":
                        try:
                            name = post["attribution"]
                            if name in top_news_titles:
                                news.append(post)
                        except KeyError:
                            pass
        return news


    @property
    def first_publishing_date(self):
        pubdates = [p.pubdate for p in self.products if p.pubdate]
        if pubdates:
            return min(pubdates)
        return None

    @property
    def openness_proportion_all_products(self):
        if not self.all_products:
            return None

        num_products = len(self.all_products)
        num_open_products = len([p for p in self.all_products if p.is_open])

        # only defined if three or more products
        if num_products >= 3:
            openness = num_open_products / float(num_products)
        else:
            openness = None

        return openness


    @property
    def openness_proportion(self):
        num_open_products_since_2007 = 0
        num_products_since_2007 = len([p for p in self.products_with_dois if p.year_int > 2007])
        for p in self.products_with_dois:
            if p.is_open_property and p.year_int > 2007:
                num_open_products_since_2007 += 1

        if num_products_since_2007 >= 3:
            openness = num_open_products_since_2007 / float(num_products_since_2007)
        else:
            openness = None

        return openness

    def set_buzz(self):
        self.buzz = None
        if self.post_counts:
            self.buzz = sum(self.post_counts.values())
        return self.buzz

    def set_influence(self):
        self.influence = None

        # from https://help.altmetric.com/support/solutions/articles/6000060969-how-is-the-altmetric-score-calculated-
        # which has later modified date than blog post with the weights etc so guesing it is the most correct version
        source_weights = {
            "news": 8,
            "blogs": 5,
            "twitter": 1,
            "googleplus": 1,
            "facebook": 0.25,
            "weibo": 1,
            "wikipedia": 3,
            "q&a": 3,
            "peer_reviews": 1,
            "f1000": 1,
            "video": 0.25,
            "reddit": 0.25,
            "pinterest": 0.25,
            "linkedin": 0.5,
            "policy": 0  # we aren't including policy
        }

        # need to have at least 3 posts for it to count
        if not self.post_counts:
            return self.influence
        if self.num_posts <= 3:
            return self.influence

        total_weight = 0
        for source, count in self.post_counts.iteritems():
            if source == "twitter":
                for p in self.products_with_dois:
                    for follower_count in p.follower_count_for_each_tweet:
                        if follower_count:
                            weight = max(1, math.log10(follower_count) - 1)
                        else:
                            weight = 1
                        total_weight += weight
            elif source in ["news", "blogs"]:
                # todo iterate through and look up.  but for now
                total_weight += source_weights[source] * count
            else:
                total_weight += source_weights[source] * count

        buzz = self.set_buzz()
        if buzz:
            self.influence = total_weight / buzz
        else:
            # otherwise undefined
            self.influence = None
        return self.influence

    def set_consistency(self):
        self.consistency = None

        if self.first_publishing_date:
            first_pub_or_2012 = max(self.first_publishing_date.isoformat(), "2012-01-01T01:00:00")

            months_since_first_pub_or_2012 = days_ago(first_pub_or_2012) / 30
            months_with_event = {}
            for event_date in self.get_event_dates():
                if event_date >= first_pub_or_2012:
                    month_string = event_date[0:7]
                    months_with_event[month_string] = True
            count_months_with_event = len(months_with_event)

            if months_since_first_pub_or_2012:
                self.consistency = count_months_with_event / float(months_since_first_pub_or_2012)

        return self.consistency

    def set_geo(self):
        self.geo = None

        post_counts_by_country = defaultdict(int)
        for p in self.products_with_dois:
            for country, count in p.post_counts_by_country.iteritems():
                post_counts_by_country[country] += count
        counts = post_counts_by_country.values()
        if counts:
            # now pad list with zeros so there's one item per country, from http://stackoverflow.com/a/3438818
            num_countries = len(country_info)
            padded_counts = counts + [0] * (num_countries - len(counts))
            self.geo = (1 - gini(padded_counts))
        print u"setting geo to {}".format(self.geo)
        return self.geo

    @property
    def display_buzz_perc(self):
        if self.buzz_perc > 0.99:
            return .99
        else:
            return self.buzz_perc

    @property
    def display_influence_perc(self):
        if self.influence_perc > 0.99:
            return .99
        else:
            return self.influence_perc

    @property
    def display_openness_perc(self):
        if self.openness_perc > 0.99:
            return .99
        else:
            return self.openness_perc


    def set_openness(self):
        self.openness = self.openness_proportion
        return self.openness

    def set_subscores(self):
        self.set_buzz()
        self.set_influence()
        self.set_openness()

    @property
    def engagement(self):
        return self.influence

    @property
    def display_engagement_perc(self):
        return self.display_influence_perc

    @property
    def subscores(self):
        config = {
            "buzz": {
                "weight": 1,
                "display_name": "buzz"
            },
            "engagement": {
                "weight": 1,
                "display_name": "engagement"
            },
            "openness": {
                "weight": .1,
                "display_name": "openness"
            },
            "fun": {
                "weight": .1,
                "display_name": "fun"
            }
        }
        ret = deepcopy(config)

        for subscore_name, subscore_dict in ret.iteritems():
            subscore_dict["name"] = subscore_name

            try:
                subscore_dict["score"] = getattr(self, subscore_name)
                subscore_dict["perc"] = getattr(self, "display_" + subscore_name + "_perc")

            except (AttributeError, TypeError):
                # there is no person.fun or person.fun_perc. move along.
                pass


        return ret.values()




    def post_counts_by_source(self, source_name):
        if self.post_counts and source_name in self.post_counts:
            return self.post_counts[source_name]
        return 0

    def set_post_counts(self):
        self.post_counts = {}

        for p in self.products_with_dois:
            if p.post_counts:
                for metric, count in p.post_counts.iteritems():
                    try:
                        self.post_counts[metric] += int(count)
                    except KeyError:
                        self.post_counts[metric] = int(count)

        # print u"setting post_counts", self.post_counts

    def set_num_sources(self):
        self.num_sources = len(self.post_counts.keys())
        # print u"set num_sources=", self.num_sources

    def set_num_posts(self):
        self.num_posts = 0
        if self.post_counts:
            self.num_posts = sum(self.post_counts.values())


    def set_num_with_metrics(self):
        if self.num_with_metrics is None:
            self.num_with_metrics = {}

        for p in self.products_with_dois:
            for metric, count in p.post_counts.iteritems():
                try:
                    self.num_with_metrics[metric] += 1
                except KeyError:
                    self.num_with_metrics[metric] = 1

        # print "setting num_with_metrics", self.num_with_metrics


    def get_token(self):
        payload = {
            'sub': self.orcid_id,
            'first_name': self.first_name,
            'family_name': self.family_name,
            'given_names': self.given_names,
            'claimed_at': date_as_iso_utc(self.claimed_at),
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=999),
        }
        token = jwt.encode(payload, os.getenv("JWT_KEY"))
        return token.decode('unicode_escape')

    @property
    def overview_badges(self):
        if len(self.active_badges) <= 3:
            return self.active_badges

        already_have_groups = []
        badges_to_return = []

        for my_badge in self.active_badges:
            if my_badge.group not in already_have_groups and my_badge.group != "fun":
                badges_to_return.append(my_badge)
                already_have_groups.append(my_badge.group)

        if len(badges_to_return) < 3:
            for my_badge in self.active_badges:
                if my_badge.group != "fun" and (my_badge.name not in [b.name for b in badges_to_return]):
                    badges_to_return.append(my_badge)

        return badges_to_return[0:3]

    @property
    def active_badges(self):
        badges = []
        for my_badge in self.badges:
            if my_badge.value and my_badge.my_badge_type.valid_badge and my_badge.my_badge_type.show_in_ui:
                # custom exclusions specific to badge type
                if my_badge.name=="reading_level" and my_badge.value > 14.0:
                    pass
                else:
                    badges.append(my_badge)

        badges.sort(key=lambda x: x.sort_score, reverse=True)


        # custom exclusions specific to badge type
        if len(badges) > 1:
            badges = [b for b in badges if b.name != "first_steps"]

        return badges

    def get_badge(self, badge_name):
        for my_badge in self.badges:
            if my_badge.name == badge_name:
                return my_badge
        return None

    def assign_badges(self, limit_to_badges=[]):

        for badge_assigner_class in badge.all_badge_assigners():

            badge_assigner = badge_assigner_class()
            if limit_to_badges:
                if badge_assigner.name not in limit_to_badges:
                    # isn't a badge we want to assign right now, so skip
                    continue

            candidate_badge = badge_assigner.get_badge_or_None(self)
            already_assigned_badge = self.get_badge(badge_assigner.name)

            if candidate_badge:
                if already_assigned_badge:
                    already_assigned_badge.level = candidate_badge.level
                    already_assigned_badge.value = candidate_badge.value
                    already_assigned_badge.products = candidate_badge.products
                    already_assigned_badge.support = candidate_badge.support
                    print u"{} already had badge, now updated {}".format(
                        self.id, already_assigned_badge)
                else:
                    print u"{} first time got badge {}".format(self.id, candidate_badge)
                    self.badges.append(candidate_badge)

                    if candidate_badge.name == 'babel':
                        print u"BABEL support: {}".format(candidate_badge.support)

            else:
                # print u"nope, {} doesn't get badge {}".format(self.id, badge_assigner.name)
                if already_assigned_badge:
                    print u"{} doesn't get badge {}, but had it before, so removing".format(self.id, badge_assigner.name)

                    if already_assigned_badge.name == 'babel':
                        print u"first, here was its BABEL support: {}".format(already_assigned_badge.support)
                        print u"used to have babel support on dois: {}".format(already_assigned_badge.dois)

                    badge.Badge.query.filter_by(id=already_assigned_badge.id).delete()


    def set_badge_percentiles(self, my_refset_list_dict):
        for my_badge in self.badges:
            if my_badge.name in badge.all_badge_assigner_names():
                my_badge.set_percentile(my_refset_list_dict[my_badge.name])

    def set_subscore_percentiles(self, my_refset_list_dict):
        self.buzz_perc = calculate_percentile(my_refset_list_dict["buzz"], self.buzz)
        self.influence_perc = calculate_percentile(my_refset_list_dict["influence"], self.influence)
        self.openness_perc = calculate_percentile(my_refset_list_dict["openness"], self.openness)



    @property
    def parsed_name(self):
        return u"{} {}".format(self.given_names, self.family_name)


    @property
    def full_name(self):
        return u"{} {}".format(self.given_names, self.family_name)


    # temp convenience, to run on a person
    def set_publisher(self):
        for p in self.products:
            p.set_publisher()

    @property
    def num_non_zero_products(self):
        return len(self.non_zero_products)

    @property
    def num_twitter_followers(self):
        try:
            return self.twitter_creds["followers_count"]
        except TypeError:
            return None


    @property
    def non_zero_products(self):
        resp = []
        for my_product in self.products_with_dois:
            if my_product.altmetric_score > 0:
                resp.append(my_product)
        return resp

    @property
    def display_coauthors(self):
        if not self.coauthors:
            return None
        else:
            ret = []
            for coauthor in self.coauthors.values():
                coauthor["sort_score"] = 0
                for val in ["buzz_perc", "engagement_perc", "openness_perc"]:
                    try:
                        coauthor["sort_score"] += coauthor.get(val, 0)
                    except TypeError:
                        pass

                ret.append(coauthor)

            return ret

    # convenience method
    def all_products_set_biblio_from_orcid(self):
        for p in self.all_products:
            p.set_biblio_from_orcid()

    @property
    def sorted_products(self):
        return sorted([p for p in self.products],
                key=lambda k: k.altmetric_score,
                reverse=True)

    @property
    def products_with_dois(self):
        ret = [p for p in self.all_products if p.doi]
        return ret

    @property
    def products_no_dois(self):
        ret = [p for p in self.all_products if not p.doi]
        return ret

    @property
    def all_products(self):
        ret = self.sorted_products
        return ret

    def __repr__(self):
        return u'<Person ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names,
            family_name=self.family_name
        )


    def to_dict(self):
        ret = {
            "_id": self.id,  # do this too, so it is on top
            "_full_name": self.full_name,
            "id": self.id,
            "orcid_id": self.orcid_id,
            "email": self.email,
            "first_name": self.first_name,
            "given_names": self.given_names,
            "family_name": self.family_name,
            "created": date_as_iso_utc(self.created),
            "updated": date_as_iso_utc(self.updated),
            "claimed_at": date_as_iso_utc(self.claimed_at),
            "picture": self.picture,
            "affiliation_name": self.affiliation_name,
            "affiliation_role_title": self.affiliation_role_title,
            "twitter": self.twitter,
            "depsy_id": self.depsy_id,
            "campaign": self.campaign,

            "num_posts": self.num_posts,
            "num_orcid_products": len(self.all_products),

            "subscores": self.subscores,
            "sources": [s.to_dict() for s in self.sources],
            "overview_badges": [b.to_dict() for b in self.overview_badges],
            "badges": [b.to_dict() for b in self.active_badges],
            "coauthors": self.display_coauthors,
            "products": [p.to_dict() for p in self.all_products],
            "num_twitter_followers": self.num_twitter_followers
        }


        # for testing! no products for jason.
        # if self.orcid_id == "0000-0001-6187-6610":
        #     ret["products"] = []

        return ret




# from http://planspace.org/2013/06/21/how-to-calculate-gini-coefficient-from-raw-data-in-python/
def gini(list_of_values):
    sorted_list = sorted(list_of_values)
    height, area = 0, 0
    for value in sorted_list:
        height += value
        area += height - value / 2.
    fair_area = height * len(list_of_values) / 2
    return (fair_area - area) / fair_area



# This takes a while.  Do it here so is part of expected boot-up.

def shortcut_all_percentile_refsets():
    refsets = shortcut_score_percentile_refsets()
    refsets.update(shortcut_badge_percentile_refsets())
    return refsets

def size_of_refset():
    # from https://gist.github.com/hest/8798884
    count_q = db.session.query(Person)
    # count_q = count_q.filter(Person.campaign == "2015_with_urls")
    count_q = count_q.statement.with_only_columns([func.count()]).order_by(None)
    count = db.session.execute(count_q).scalar()
    print "refsize count", count
    return count

def shortcut_score_percentile_refsets():
    print u"getting the score percentile refsets...."
    refset_list_dict = defaultdict(list)
    q = db.session.query(
        Person.buzz,
        Person.influence,
        Person.openness
    )
    q = q.filter(Person.score != 0)
    rows = q.all()

    num_in_refset = size_of_refset()

    print u"query finished, now set the values in the lists"
    refset_list_dict["buzz"] = [row[0] for row in rows if row[0] != None]
    refset_list_dict["buzz"].extend([0] * (num_in_refset - len(refset_list_dict["buzz"])))

    refset_list_dict["influence"] = [row[1] for row in rows if row[1] != None]
    # don't zero pad this one!

    refset_list_dict["openness"] = [row[2] for row in rows if row[2] != None]
    # don't zero pad this one!

    for name, values in refset_list_dict.iteritems():
        # now sort
        refset_list_dict[name] = sorted(values)

    return refset_list_dict



def shortcut_badge_percentile_refsets():
    print u"getting the badge percentile refsets...."
    refset_list_dict = defaultdict(list)
    q = db.session.query(
        badge.Badge.name,
        badge.Badge.value,
    )
    q = q.filter(badge.Badge.value != None)
    rows = q.all()

    print u"query finished, now set the values in the lists"
    for row in rows:
        if row[1]:
            refset_list_dict[row[0]].append(row[1])

    num_in_refset = size_of_refset()

    for name, values in refset_list_dict.iteritems():
        assigner = badge.get_badge_assigner(name)
        if assigner.pad_percentiles_with_zeros:
            # pad with zeros for all the people who didn't get the badge
            values.extend([0] * (num_in_refset - len(values)))

        # now sort
        refset_list_dict[name] = sorted(values)

    return refset_list_dict

def get_refsets():
    refsets = None
    start_time = time()
    if os.getenv("IS_LOCAL", False) == "True":
        print u"Not loading refsets because IS_LOCAL. Will not set percentiles when creating or refreshing profiles."
    else:
        refsets = shortcut_badge_percentile_refsets()
        refsets.update(shortcut_score_percentile_refsets())
    print u"finished with refsets in {}s".format(elapsed(start_time))
    return refsets

refsets = get_refsets()
