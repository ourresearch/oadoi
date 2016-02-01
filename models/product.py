from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
from util import remove_nonprinting_characters
import json
import shortuuid
import requests
import os
import re

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

    # get the title
    try:
        product.title = str(product_dict['work-title']['title']['value'].encode('utf-8'))
    except TypeError:
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

    return matches[0]





class Product(db.Model):
    id = db.Column(db.Text, primary_key=True)
    title = db.Column(db.Text)
    year = db.Column(db.Text)
    doi = db.Column(db.Text)
    api_raw = db.Column(db.Text)
    orcid = db.Column(db.Text, db.ForeignKey('profile.id'))

    altmetric_api_raw = db.Column(db.Text)
    altmetric_counts = db.Column(MutableDict.as_mutable(JSONB))
    altmetric_detail_api_raw = db.Column(JSONB)

    altmetric_score = db.Column(db.Float)
    event_dates = db.Column(JSONB)


#### Doesn't yet include Mendeley, Citeulike, or Connotea
####  add that code before running this and expecting all results :)
    def set_altmetric_counts(self):
        self.altmetric_counts = {}        
        if not self.altmetric_detail_api_raw:
            return

        exclude_keys = "total"
        for k in self.altmetric_detail_api_raw["counts"]:
            if k not in exclude_keys:
                source = k
                count = int(self.altmetric_detail_api_raw["counts"][source]["posts_count"])
                self.altmetric_counts[source] = count
                print u"setting {source} to {count} for {doi}".format(
                    source=source,
                    count=count,
                    doi=self.doi)


    def set_altmetric_score(self):
        self.altmetric_score = 0        
        if not self.altmetric_detail_api_raw:
            return

        self.altmetric_score = self.altmetric_detail_api_raw["score"]


    def set_event_dates(self):
        self.event_dates = []        
        if not self.altmetric_detail_api_raw:
            return
        if "posts" not in self.altmetric_detail_api_raw:
            return
        if not self.altmetric_detail_api_raw["posts"]:
            return

        for source, posts in self.altmetric_detail_api_raw["posts"].iteritems():
            for post in posts:
                post_date = post["posted_on"]
                self.event_dates.append(post_date)

        if self.event_dates:
            self.event_dates.sort(reverse=True) 
             
        # print u"self.event_dates are {dates} for {doi}".format(
        #     dates=self.event_dates,
        #     doi=self.doi)


    # only gets tweets
    def set_altmetric_detail_api_raw(self):
        url = u"http://api.altmetric.com/v1/fetch/doi/{doi}?key={key}".format(
            doi=self.clean_doi,
            key=os.getenv("ALTMETRIC_KEY")
        )

        print u"calling /fetch for altmetric.com: {}".format(url)

        r = requests.get(url)

        # Altmetric.com doesn't have this DOI. It has no metrics.
        if r.status_code == 404:
            self.altmetric_detail_api_raw = {}
        else:
            # we got a good status code, the DOI has metrics.
            print u"got metrics for {doi}".format(doi=self.doi)
            try:
                self.altmetric_detail_api_raw = r.json()
            except ValueError:  # includes simplejson.decoder.JSONDecodeError
                print u"Decoding JSON has failed for {doi}, got {text}, so skipping".format(
                    doi=self.doi,
                    text=r.text)
                # set runmarker
                self.altmetric_detail_api_raw = {}


    # only gets tweeters not tweets
    def set_altmetric_summary_counts(self):

        url = u"http://api.altmetric.com/v1/doi/{doi}?key={key}".format(
            doi=self.clean_doi,
            key=os.getenv("ALTMETRIC_KEY")
        )

        print u"calling altmetric.com: {}".format(url)

        r = requests.get(url)
        if not self.altmetric_counts:
            self.altmetric_counts = {}

        # Altmetric.com doesn't have this DOI. It has no metrics.
        if r.status_code == 404:
            self.altmetric_api_raw = False  # run marker
            self.altmetric_counts = {}  # maybe the DOI went away, so reset counts.
            return False


        # we got a good status code, the DOI has metrics.
        self.altmetric_api_raw = r.text
        print u"got metrics for {doi}".format(doi=self.doi)        
        for k, v in r.json().iteritems():
            if k.startswith("cited_by_"):
                short_key = k.replace("cited_by_", "").replace("_count", "")
                self.altmetric_counts[short_key] = v

        try:
            mendeley_count_str = r.json()["readers"]["mendeley"]
            if mendeley_count_str:
                self.altmetric_counts["mendeley"] = int(mendeley_count_str)
        except KeyError:
            pass


        return True

    @property
    def display_title(self):
        if self.title:
            return self.title
        else:
            return "No title"

    @property
    def clean_doi(self):
        # this shouldn't be necessary because we clean DOIs
        # before we put them in. however, there are a few legacy ones that were
        # not fully cleaned. this is to deal with them.
        return clean_doi(self.doi)

    def __repr__(self):
        return u'<Product ({id})>'.format(
            id=self.id
        )

    def to_dict(self):
        return {
            "id": self.id,
            "doi": self.doi,
            "orcid": self.orcid,
            "title": self.title,
            "year": self.year
        }





