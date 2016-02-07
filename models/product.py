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

    altmetric_api_raw = db.Column(JSONB)
    altmetric_counts = db.Column(MutableDict.as_mutable(JSONB))

    altmetric_score = db.Column(db.Float)
    event_dates = db.Column(JSONB)


    #### Doesn't yet include Mendeley, Citeulike, or Connotea
    ####  add that code before running this and expecting all results :)
    def set_altmetric_counts(self):
        self.altmetric_counts = {}        
        if not self.altmetric_api_raw:
            return

        exclude_keys = "total"
        for k in self.altmetric_api_raw["counts"]:
            if k not in exclude_keys:
                source = k
                count = int(self.altmetric_api_raw["counts"][source]["posts_count"])
                self.altmetric_counts[source] = count
                print u"setting {source} to {count} for {doi}".format(
                    source=source,
                    count=count,
                    doi=self.doi)


    def set_altmetric_score(self):
        self.altmetric_score = 0        
        if not self.altmetric_api_raw:
            return

        self.altmetric_score = self.altmetric_api_raw["score"]


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


    def set_altmetric_api_raw(self):
        url = u"http://api.altmetric.com/v1/fetch/doi/{doi}?key={key}".format(
            doi=self.clean_doi,
            key=os.getenv("ALTMETRIC_KEY")
        )

        print u"calling /fetch for altmetric.com: {}".format(url)

        r = requests.get(url)

        # Altmetric.com doesn't have this DOI, so the DOI has no metrics.
        if r.status_code == 404:
            self.altmetric_api_raw = {"error": "404"}
        else:
            # we got a good status code, the DOI has metrics.
            print u"got metrics for {doi}".format(doi=self.doi)
            try:
                self.altmetric_api_raw = r.json()
            except ValueError:  # includes simplejson.decoder.JSONDecodeError
                print u"Decoding JSON has failed for {doi}, got {text}, so skipping".format(
                    doi=self.doi,
                    text=r.text)

                # set runmarker
                self.altmetric_api_raw = {"error": "Altmetric.com msg: '{}'".format(r.text)}


    # def get_altmetric_counts_from_summary(self, api_raw_text):
    #     altmetric_counts = {}
    #
    #     try:
    #         json_data = json.loads(api_raw_text)
    #     except ValueError:
    #         print u"Couldn't decode json {} for {}".format(api_raw_text, self.doi)
    #         raise  # don't just pass through; we want to see all of these
    #
    #
    #     if json_data == False:
    #         return altmetric_counts
    #
    #     for k, v in json_data.iteritems():
    #         if k.startswith("cited_by_"):
    #             short_key = k.replace("cited_by_", "").replace("_count", "")
    #             altmetric_counts[short_key] = v
    #
    #     try:
    #         mendeley_count_str = json_data["readers"]["mendeley"]
    #         if mendeley_count_str:
    #             altmetric_counts["mendeley"] = int(mendeley_count_str)
    #     except KeyError:
    #         pass
    #
    #     return altmetric_counts



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
        print u"got metrics for {doi}".format(doi=self.doi)        
        self.altmetric_api_raw = r.text
        print r.text
        self.altmetric_counts = self.get_altmetric_counts_from_summary(self.altmetric_api_raw)

        return True

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
            "altmetric_score": self.altmetric_score,
            "year": self.year,
            "title": self.title,
            "altmetric_counts": self.altmetric_counts_tuples,
        }





