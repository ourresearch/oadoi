from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import deferred
from collections import defaultdict

import json
import shortuuid
import datetime

from app import db


preprint_url_fragments = [
    "/npre.",
    "10.15200/winn.",
    "/f1000research.",
    "/peerj.preprints",
    ".figshare.",
    "/10.1101/"  #biorxiv
]

dataset_url_fragments = [
                 "/dryad.",
                 "/zenodo."
                 ]

open_url_fragments = preprint_url_fragments + dataset_url_fragments



def make_non_doi_product(orcid_product_dict):
    non_doi_product = NonDoiProduct()
    non_doi_product.orcid_api_raw = json.dumps(orcid_product_dict)
    return non_doi_product

    #
    # # get the url
    # doi = None
    #
    # if orcid_product_dict.get('work-external-identifiers', []):
    #     for x in orcid_product_dict.get('work-external-identifiers', []):
    #         for eid in orcid_product_dict['work-external-identifiers']['work-external-identifier']:
    #             if eid['work-external-identifier-type'] == 'DOI':
    #                 try:
    #                     id_string = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()
    #                     doi = clean_doi(id_string)  # throws error unless valid DOI
    #                 except (TypeError, NoDoiException):
    #                     doi = None
    # if not doi:
    #     # try url
    #     try:
    #         id_string = str(orcid_product_dict['url']['value'].encode('utf-8')).lower()
    #         if is_doi_url(id_string):
    #             doi = clean_doi(id_string)  # throws error unless valid DOI
    #     except (TypeError, NoDoiException):
    #         doi = None
    #
    # if not doi:
    #     raise NoDoiException
    #
    # product.doi = doi
    # if "work-type" in orcid_product_dict:
    #     product.type = str(orcid_product_dict['work-type'].encode('utf-8')).lower()
    # product.api_raw = json.dumps(orcid_product_dict)
    # return product



class NonDoiProduct(db.Model):
    id = db.Column(db.Text, primary_key=True)
    url = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)

    title = db.Column(db.Text)
    journal = db.Column(db.Text)
    type = db.Column(db.Text)
    pubdate = db.Column(db.DateTime)
    year = db.Column(db.Text)
    authors = db.Column(db.Text)

    orcid_api_raw = db.Column(db.Text)
    in_doaj = db.Column(db.Boolean)

    error = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        super(NonDoiProduct, self).__init__(**kwargs)

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

    def __repr__(self):
        return u'<NonDoiProduct ({id}) {doi}>'.format(
            id=self.id,
            doi=self.doi
        )

    def guess_genre(self):
        if self.type:
            if self.type and "data" in self.type:
                return "dataset"
            elif any(fragment in self.url for fragment in dataset_url_fragments):
                return "dataset"
            elif self.type and "poster" in self.type:
                return "poster"
            elif self.type and "abstract" in self.type:
                return "abstract"
            elif ".figshare." in self.url:
                if self.type:
                    if ("article" in self.type or "paper" in self.type):
                        return "preprint"
                    else:
                        return self.type.replace("_", "-")
                else:
                    return "preprint"
            elif any(fragment in self.url for fragment in preprint_url_fragments):
                return "preprint"
        return "article"


    def to_dict(self):
        return {
            "id": self.id,
            "doi": None,
            "url": self.url,
            "orcid_id": self.orcid_id,
            "year": self.year,
            "title": self.title,
            "journal": self.journal,
            "authors": self.authors,
            "altmetric_id": None,
            "altmetric_score": None,
            "num_posts": 0,
            "is_oa_journal": False,
            "is_oa_repository": False,
            "is_open": False,
            "sources": [],
            "posts": [],
            "events_last_week_count": 0,
            "genre": self.guess_genre()
        }





