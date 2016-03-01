from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
from util import remove_nonprinting_characters
import json
import shortuuid
import requests
import os
import re
import logging

class NoDoiException(Exception):
    pass

def make_product(product_dict):
    shortuuid.set_alphabet('abcdefghijklmnopqrstuvwxyz1234567890')
    product = Product(id=shortuuid.uuid()[0:10])

    # get the DOI
    dirty_doi = None
    if product_dict.get('work-external-identifiers', []):
        for x in product_dict.get('work-external-identifiers', []):
            for eid in product_dict['work-external-identifiers']['work-external-identifier']:
                if eid['work-external-identifier-type'] == 'DOI':
                    dirty_doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()

    product.doi = clean_doi(dirty_doi)  # throws error unless valid DOI

    # get the title
    try:
        product.title = str(product_dict['work-title']['title']['value'].encode('utf-8'))
    except (TypeError, UnicodeDecodeError):
        product.title = None

    # get the publication date
    pub_date = product_dict.get('publication-date', None)
    if pub_date:
        product.year = pub_date.get('year', None).get('value').encode('utf-8')
    else:
        product.year = None

    product.api_raw = json.dumps(product_dict)
    product.altmetric_api_raw = None
    product.altmetric_counts = {}

    product.set_altmetric_score()

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
    title = db.Column(db.Text)
    year = db.Column(db.Text)
    doi = db.Column(db.Text)
    api_raw = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))

    altmetric_api_raw = db.Column(JSONB)
    post_counts = db.Column(MutableDict.as_mutable(JSONB))
    poster_counts = db.Column(MutableDict.as_mutable(JSONB))

    altmetric_score = db.Column(db.Float)
    event_dates = db.Column(JSONB)

    error = db.Column(db.Text)

    def set_data_from_altmetric(self, high_priority=False):
        self.set_altmetric_api_raw(high_priority)
        self.set_post_counts()
        self.set_poster_counts()


    def set_post_counts(self):
        self.post_counts = {}
        if not self.altmetric_api_raw:
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
        if not self.altmetric_api_raw:
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

    def set_altmetric_score(self):
        self.altmetric_score = 0        

        try:
            self.altmetric_score = self.altmetric_api_raw["altmetric_score"]["score"]
            print "set score to", self.altmetric_score
        except (KeyError, TypeError):
            pass


    def set_event_dates(self):
        self.event_dates = []        
        if not self.altmetric_api_raw:
            return
        if "posts" not in self.altmetric_api_raw:
            return
        if not self.altmetric_api_raw["posts"]:
            return

        for source, posts in self.altmetric_api_raw["posts"].iteritems():
            for post in posts:
                post_date = post["posted_on"]
                self.event_dates.append(post_date)

        if self.event_dates:
            self.event_dates.sort(reverse=True) 

        # print u"self.event_dates are {dates} for {doi}".format(
        #     dates=self.event_dates,
        #     doi=self.doi)


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

            # and just for interest, print this too
            daily_rate_limit_remaining = int(r.headers["x-dailyratelimit-remaining"])
            if daily_rate_limit_remaining != 86400:
                print u"daily_rate_limit_remaining=", daily_rate_limit_remaining

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




    @property
    def altmetric_counts_tuples(self):
        self.altmetric_counts = self.get_altmetric_counts_from_summary(self.altmetric_api_raw)
        if self.altmetric_counts:
            return self.altmetric_counts.items()
        else:
            return []

    @property
    def display_title(self):
        if self.title:
            return self.title
        else:
            return "No title"

    @property
    def year_int(self):
        if not self.year:
            return None
        return int(self.year)

    @property
    def clean_doi(self):
        # this shouldn't be necessary because we clean DOIs
        # before we put them in. however, there are a few legacy ones that were
        # not fully cleaned. this is to deal with them.
        return clean_doi(self.doi)

    def __repr__(self):
        return u'<Product ({id}) {doi} {orcid_id} {score}>'.format(
            id=self.id,
            doi=self.doi,
            orcid_id=self.orcid_id,
            score=self.altmetric_score
        )

    def to_dict(self):
        # @todo add these back in once we've calculated them again...
        return {
            "id": self.id,
            "doi": self.doi,
            "orcid_id": self.orcid_id,
            # "altmetric_score": self.altmetric_score,
            "year": self.year,
            "title": self.title,
            # "altmetric_counts": self.altmetric_counts_tuples,
        }





