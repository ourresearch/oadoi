from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db
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

    # AIP journals tend to have a \n in the DOI, and the doi is the second line.
    # we get that here. put this in the validation function later.
    if len(dirty_doi.split('\n')) == 2:
        dirty_doi = dirty_doi.split('\n')[1]

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



    def set_altmetric(self):
        url = "http://api.altmetric.com/v1/doi/{doi}?key={key}".format(
            doi=self.doi,
            key=os.getenv("ALTMETRIC_KEY")
        )

        print "calling altmetric.com: {}".format(url)

        r = requests.get(url)
        if not self.altmetric_counts:
            self.altmetric_counts = {}

        # Altmetric.com doesn't know have this DOI. It has no metrics.
        if r.status_code == 404:
            self.altmetric_api_raw = False  # run marker
            self.altmetric_counts = {}  # maybe the DOI went away, so reset counts.
            return False


        # we got a good status code, the DOI has metrics.
        self.altmetric_api_raw = r.text
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

    def __repr__(self):
        return u'<Product ({id}) "{title}" >'.format(
            id=self.id,
            title=self.display_title
        )

    def to_dict(self):
        return {
            "id": self.id,
            "doi": self.doi,
            "orcid": self.orcid,
            "title": self.title,
            "year": self.year
        }





