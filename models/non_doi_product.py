from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import deferred
from collections import defaultdict

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
    "/10.1101/"  #biorxiv
]

dataset_url_fragments = [
                 "/dryad.",
                 "/zenodo."
                 ]

open_url_fragments = preprint_url_fragments + dataset_url_fragments



def make_non_doi_product(orcid_product_dict):
    non_doi_product = NonDoiProduct()
    non_doi_product.set_biblio_from_biblio_dict(orcid_product_dict)
    non_doi_product.orcid_api_raw = json.dumps(orcid_product_dict)

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

    orcid_api_raw = db.Column(db.Text)
    in_doaj = db.Column(db.Boolean)

    error = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        super(NonDoiProduct, self).__init__(**kwargs)

    def set_biblio_from_orcid(self):
        if not self.orcid_api_raw:
            print u"no self.orcid_api_raw for non_doi_product {}".format(self.id)
        orcid_biblio_dict = json.loads(self.orcid_api_raw)
        self.set_biblio_from_biblio_dict(orcid_biblio_dict)

    def set_biblio_from_biblio_dict(self, biblio_dict):

        try:
            self.type = biblio_dict["work-type"].lower().replace("_", "-")
        except (TypeError, KeyError):
            pass

        # replace many white spaces and \n with just one space
        try:
            self.title = re.sub(u"\s+", u" ", biblio_dict["work-title"]["title"]["value"])
        except (TypeError, KeyError):
            pass

        try:
            self.journal = biblio_dict["journal-title"]["value"]
        except (TypeError, KeyError):
            pass

        # just get year for now
        try:
            self.year = biblio_dict["publication-date"]["year"]["value"]
        except (TypeError, KeyError):
            pass

        try:
            self.url = biblio_dict["url"]["value"]
        except (TypeError, KeyError):
            pass

        # not doing authors yet
        # not doing work-external-identifiers yet



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





