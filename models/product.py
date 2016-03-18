from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import deferred
from collections import defaultdict
import langdetect
import json
import shortuuid
import requests
import os
import re
import logging

from app import db
from util import remove_nonprinting_characters

from models.source import sources_metadata
from models.source import Source
from models.country import country_info
from models.country import get_name_from_iso
from models.language import get_language_from_abbreviation


class NoDoiException(Exception):
    pass

def make_product(product_dict):
    product = Product(id=shortuuid.uuid()[0:10])

    # get the DOI
    dirty_doi = None
    if product_dict.get('work-external-identifiers', []):
        for x in product_dict.get('work-external-identifiers', []):
            for eid in product_dict['work-external-identifiers']['work-external-identifier']:
                if eid['work-external-identifier-type'] == 'DOI':
                    dirty_doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()

    product.doi = clean_doi(dirty_doi)  # throws error unless valid DOI
    product.api_raw = json.dumps(product_dict)
    return product


def clean_doi(dirty_doi):
    if not dirty_doi:
        raise NoDoiException("There's no valid DOI.")

    dirty_doi = remove_nonprinting_characters(dirty_doi)
    dirty_doi = dirty_doi.strip()

    # test cases for this regex are at https://regex101.com/r/zS4hA0/1
    p = re.compile(ur'.*?(10.+)')

    matches = re.findall(p, dirty_doi)
    if len(matches) == 0:
        raise NoDoiException("There's no valid DOI.")

    match = matches[0]
    try:
        resp = unicode(match, "utf-8")  # unicode is valid in dois
    except (TypeError, UnicodeDecodeError):
        resp = match

    return match





class Product(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))

    title = db.Column(db.Text)
    journal = db.Column(db.Text)
    type = db.Column(db.Text)
    pubdate = db.Column(db.DateTime)
    year = db.Column(db.Text)

    api_raw = db.Column(db.Text)
    altmetric_api_raw = deferred(db.Column(JSONB))
    altmetric_id = db.Column(db.Text)

    altmetric_score = db.Column(db.Float)
    post_counts = db.Column(MutableDict.as_mutable(JSONB))
    poster_counts = db.Column(MutableDict.as_mutable(JSONB))
    event_dates = db.Column(MutableDict.as_mutable(JSONB))

    error = db.Column(db.Text)



    def set_data_from_altmetric(self, high_priority=False):
        # set_altmetric_api_raw catches its own errors, but since this is the method
        # called by the thread from Person.set_data_from_altmetric_for_all_products
        # want to have defense in depth and wrap this whole thing in a try/catch too
        # in case errors in calculate_metrics or anything else we add.
        try:
            self.set_altmetric_api_raw(high_priority)
            self.calculate_metrics()
        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except Exception:
            logging.exception("exception in set_data_from_altmetric")
            self.error = "error in set_data_from_altmetric"
            print self.error

    def calculate_metrics(self):
        self.set_biblio()
        self.set_altmetric_score()
        self.set_altmetric_id()
        self.set_post_counts()
        self.set_poster_counts()
        self.set_event_dates()


    def set_biblio(self):
        try:
            biblio_dict = self.altmetric_api_raw["citation"]
            self.title = biblio_dict["title"]
            self.journal = biblio_dict["journal"]
            self.type = biblio_dict["type"]
            if "pubdate" in biblio_dict:
                self.pubdate = biblio_dict["pubdate"]
            else:
                self.pubdate = biblio_dict["first_seen_on"]
            self.year = self.pubdate[0:4]
        except (KeyError, TypeError):
            # doesn't always have citation (if error)
            # and sometimes citation only includes the doi
            pass

    def set_altmetric_score(self):
        self.altmetric_score = 0
        try:
            self.altmetric_score = self.altmetric_api_raw["score"]
            print u"set score to", self.altmetric_score
        except (KeyError, TypeError):
            pass


    def post_counts_by_source(self, source):
        if source in self.post_counts:
            return self.post_counts[source]
        return 0



    def set_post_counts(self):
        self.post_counts = {}
        if not self.altmetric_api_raw or "counts" not in self.altmetric_api_raw:
            return

        exclude_keys = ["total", "readers"]
        for k in self.altmetric_api_raw["counts"]:
            if k not in exclude_keys:
                source = k
                count = int(self.altmetric_api_raw["counts"][source]["posts_count"])
                self.post_counts[source] = count
                print u"setting posts for {source} to {count} for {doi}".format(
                    source=source,
                    count=count,
                    doi=self.doi)


    def set_poster_counts(self):
        self.poster_counts = {}
        if not self.altmetric_api_raw or "counts" not in self.altmetric_api_raw:
            return

        exclude_keys = ["total", "readers"]
        for k in self.altmetric_api_raw["counts"]:
            if k not in exclude_keys:
                source = k
                count = int(self.altmetric_api_raw["counts"][source]["unique_users_count"])
                self.poster_counts[source] = count
                print u"setting posters for {source} to {count} for {doi}".format(
                    source=source,
                    count=count,
                    doi=self.doi)


    def set_event_dates(self):
        self.event_dates = {}

        if not self.altmetric_api_raw or "posts" not in self.altmetric_api_raw:
            return
        if self.altmetric_api_raw["posts"] == []:
            return

        for source, posts in self.altmetric_api_raw["posts"].iteritems():
            for post in posts:
                post_date = post["posted_on"]
                if source not in self.event_dates:
                    self.event_dates[source] = []
                self.event_dates[source].append(post_date)

        # now sort them all
        for source in self.event_dates:
            self.event_dates[source].sort(reverse=False)
            print u"set event_dates for {} {}".format(self.doi, source)



    def set_altmetric_api_raw(self, high_priority=False):
        try:
            self.error = None

            url = u"http://api.altmetric.com/v1/fetch/doi/{doi}?key={key}".format(
                doi=self.clean_doi,
                key=os.getenv("ALTMETRIC_KEY")
            )
            print u"calling {}".format(url)

            # might throw requests.Timeout
            r = requests.get(url, timeout=10)  #timeout in seconds

            # handle rate limit stuff even before parsing this response
            hourly_rate_limit_remaining = int(r.headers["x-hourlyratelimit-remaining"])
            if hourly_rate_limit_remaining != 3600:
                print u"hourly_rate_limit_remaining=", hourly_rate_limit_remaining

            if (hourly_rate_limit_remaining < 500 and not high_priority) or \
                    r.status_code == 420:
                print u"sleeping for an hour until we have more calls remaining"
                sleep(60*60) # an hour

            # Altmetric.com doesn't have this DOI, so the DOI has no metrics.
            if r.status_code == 404:
                # altmetric.com doesn't have any metrics for this doi
                self.altmetric_api_raw = {"error": "404"}
            elif r.status_code == 420:
                self.error = "hard-stop rate limit error setting altmetric.com metrics"
            elif r.status_code == 200:
                # we got a good status code, the DOI has metrics.
                self.altmetric_api_raw = r.json()
                print u"yay nonzero metrics for {doi}".format(doi=self.doi)
            else:
                self.error = u"got unexpected status_code code {}".format(r.status_code)

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "timeout error setting altmetric.com metrics"
        except Exception:
            logging.exception("exception in set_altmetric_api_raw")
            self.error = "error setting altmetric.com metrics"
        finally:
            if self.error:
                print self.error

    def set_altmetric_id(self):
        try:
            self.altmetric_id = self.altmetric_api_raw["altmetric_id"]
        except (KeyError, TypeError):
            self.altmetric_id = None


    #@todo actually add whether this is OA or not
    @property
    def is_oa_article(self):
        if (not self.type) or self.type == "article":
            return True
        return False

    @property
    def sources(self):
        sources = []
        for source_name in sources_metadata:
            source = Source(source_name, [self])
            if source.posts_count > 0:
                sources.append(source)
        return sources

    @property
    def events_last_week_count(self):
        events_last_week_count = 0
        for source in self.sources:
            events_last_week_count += source.events_last_week_count
        return events_last_week_count

    @property
    def display_title(self):
        if self.title:
            return self.title
        else:
            return "No title"

    @property
    def year_int(self):
        if not self.year:
            return 0
        return int(self.year)

    @property
    def countries(self):
        return [get_name_from_iso(my_country) for my_country in self.post_counts_by_country.keys()]

    @property
    def post_counts_by_country(self):
        try:
            resp = self.altmetric_api_raw["demographics"]["geo"]["twitter"]
        except (KeyError, TypeError):
            resp = {}
        return resp

    @property
    def poster_counts_by_type(self):
        try:
            resp = self.altmetric_api_raw["demographics"]["users"]["twitter"]["cohorts"]
            if not resp:
                resp = {}
        except (KeyError, TypeError):
            resp = {}
        return resp

    def has_source(self, source_name):
        if self.post_counts:
            return (source_name in self.post_counts)
        return False

    @property
    def impressions(self):
        return sum(self.twitter_posters_with_followers.values())


    @property
    def tweeter_posters_full_names(self):
        names = []
        try:
            for post in self.altmetric_api_raw["posts"]["twitter"]:
                names.append(post["author"]["name"])
        except (KeyError, TypeError):
            pass
        return names

    @property
    def twitter_posters_with_followers(self):
        posters = {}
        try:
            for post in self.altmetric_api_raw["posts"]["twitter"]:
                poster = post["author"]["id_on_source"]
                followers = post["author"]["followers"]
                posters[poster] = followers
        except (KeyError, TypeError):
            posters = {}
        return posters


    def f1000_urls_for_class(self, f1000_class):
        urls = []
        try:
            for post in self.altmetric_api_raw["posts"]["f1000"]:
                if f1000_class in post["f1000_classes"]:
                    urls.append(u"<a href='{}'>Review</a>".format(post["url"]))
        except (KeyError, TypeError):
            urls = []
        return urls

    @property
    def impact_urls(self):
        try:
            urls = self.altmetric_api_raw["citation"]["links"]
        except (KeyError, TypeError):
            urls = []
        return urls

    @property
    def languages_with_examples(self):
        resp = {}

        try:
            for (source, posts) in self.altmetric_api_raw["posts"].iteritems():
                for post in posts:
                    for key in ["title", "summary"]:
                        try:
                            num_words_in_post = len(post[key].split(" "))
                            top_detection = langdetect.detect_langs(post[key])[0]
                            if (num_words_in_post > 7) and (top_detection.prob > 0.90):

                                if top_detection.lang != "en":
                                    language_name = get_language_from_abbreviation(top_detection.lang)
                                    # print u"LANGUAGE:", language_name, top_detection.prob, post[key]

                                    # overwrites.  that's ok, we just want one example
                                    resp[language_name] = post["url"]

                        except langdetect.lang_detect_exception.LangDetectException:
                            pass

        except (KeyError, AttributeError, TypeError):
            pass

        return resp


    @property
    def publons_reviews(self):
        reviews = []
        try:
            for post in self.altmetric_api_raw["posts"]["peer_reviews"]:
                if post["pr_id"] == "publons":
                    reviews.append({
                        "url": post["publons_article_url"],
                        "publons_weighted_average": post["publons_weighted_average"]
                    })
        except (KeyError, TypeError):
            reviews = []
        return reviews

    @property
    def wikipedia_urls(self):
        articles = []
        try:
            for post in self.altmetric_api_raw["posts"]["wikipedia"]:
                articles.append(u"<a href='{}'>{}</a>".format(
                    post["page_url"],
                    post["title"]))
        except (KeyError, TypeError):
            articles = []
        return articles

    def has_country(self, country_name):
        try:
            iso_name = country_info[country_name]["iso"]
        except KeyError:
            print u"****ERRROR couldn't find country {} in lookup table".format(country_name)
            raise # don't continue, fix this immediately.  shouldn't happen unexpectedly at runtime

        return (iso_name in self.countries)



    @property
    def clean_doi(self):
        # this shouldn't be necessary because we clean DOIs
        # before we put them in. however, there are a few legacy ones that were
        # not fully cleaned. this is to deal with them.
        return clean_doi(self.doi)

    def __repr__(self):
        return u'<Product ({id}) {doi}>'.format(
            id=self.id,
            doi=self.doi
        )

    def to_dict(self):
        return {
            "id": self.id,
            "doi": self.doi,
            "orcid_id": self.orcid_id,
            "year": self.year,
            "title": self.title,
            "journal": self.journal,
            "altmetric_id": self.altmetric_id,
            "altmetric_score": self.altmetric_score,
            "sources": [s.to_dict() for s in self.sources],
            "events_last_week_count": self.events_last_week_count
        }





