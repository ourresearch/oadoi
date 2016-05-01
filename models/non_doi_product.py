from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import deferred
from collections import defaultdict
from models.orcid import set_biblio_from_biblio_dict
from util import normalize

import json
import shortuuid
import datetime
import re

from app import db


preprint_url_fragments = [
    "/npre.",
    "10.15200/winn.",
    "/f1000research.",
    "/peerj.preprints",
    ".figshare.",
    "10.1101/"  #biorxiv
]

dataset_url_fragments = [
                 "/dryad.",
                 "/zenodo."
                 ]

open_url_fragments = preprint_url_fragments + dataset_url_fragments



def make_non_doi_product(orcid_product_dict):
    non_doi_product = NonDoiProduct()
    set_biblio_from_biblio_dict(non_doi_product, orcid_product_dict)
    non_doi_product.orcid_api_raw = json.dumps(orcid_product_dict)
    # non_doi_product.set_is_open()

    return non_doi_product


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
    orcid_put_code = db.Column(db.Text)
    orcid_importer = db.Column(db.Text)

    orcid_api_raw = db.Column(db.Text)
    in_doaj = db.Column(db.Boolean)
    is_open = db.Column(db.Boolean)
    open_url = db.Column(db.Text)
    open_urls = db.Column(MutableDict.as_mutable(JSONB))  #change to list when upgrade to sqla 1.1

    error = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        super(NonDoiProduct, self).__init__(**kwargs)

    def set_biblio_from_orcid(self):
        if not self.orcid_api_raw:
            print u"no self.orcid_api_raw for non_doi_product {}".format(self.id)
        orcid_biblio_dict = json.loads(self.orcid_api_raw)
        set_biblio_from_biblio_dict(self, orcid_biblio_dict)



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
        return u'<NonDoiProduct ({id}) {url}>'.format(
            id=self.id,
            url=self.url
        )

    def guess_genre(self):
        if self.type:
            if "data" in self.type:
                return "dataset"
            elif self.url and any(fragment in self.url for fragment in dataset_url_fragments):
                return "dataset"
            elif "poster" in self.type:
                return "poster"
            elif "abstract" in self.type:
                return "abstract"
            elif self.url and ".figshare." in self.url:
                if self.type:
                    if ("article" in self.type or "paper" in self.type):
                        return "preprint"
                    else:
                        return self.type.replace("_", "-")
                else:
                    return "preprint"
            elif self.url and any(fragment in self.url for fragment in preprint_url_fragments):
                return "preprint"
            elif "article" in self.type:
                return "article"
            else:
                return self.type.replace("_", "-")
        return "article"


    def to_dict(self):
        return {
            "id": self.id,
            "doi": None,
            "url": self.url,
            "orcid_id": self.orcid_id,
            "year": self.year,
            "title": self.display_title,
            # "title_normalized": normalize(self.display_title),
            "journal": self.journal,
            "authors": self.authors,
            "altmetric_id": None,
            "altmetric_score": None,
            "num_posts": 0,
            "is_oa_journal": False,
            "is_oa_repository": False,
            "is_open": False,
            "is_open_new": self.is_open,
            "open_url": self.open_url,
            "open_urls": self.open_urls,
            "sources": [],
            "posts": [],
            "events_last_week_count": 0,
            "genre": self.guess_genre()
        }





