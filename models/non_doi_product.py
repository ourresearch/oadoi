from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import deferred
from collections import defaultdict
from models.orcid import set_biblio_from_biblio_dict
from util import normalize

from models.oa import dataset_url_fragments
from models.oa import preprint_url_fragments

import json
import shortuuid
import datetime
import re
import requests

from app import db


def make_non_doi_product(orcid_product_dict):
    non_doi_product = NonDoiProduct()
    set_biblio_from_biblio_dict(non_doi_product, orcid_product_dict)
    non_doi_product.orcid_api_raw_json = orcid_product_dict

    # self.try_to_set_doi()

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
    authors = deferred(db.Column(db.Text))
    authors_short = db.Column(db.Text)
    orcid_put_code = db.Column(db.Text)
    orcid_importer = db.Column(db.Text)
    doi = db.Column(db.Text)

    orcid_api_raw_json = deferred(db.Column(JSONB))
    in_doaj = db.Column(db.Boolean)
    is_open = db.Column(db.Boolean)
    open_url = db.Column(db.Text)
    open_urls = db.Column(MutableDict.as_mutable(JSONB))  #change to list when upgrade to sqla 1.1
    base_dcoa = db.Column(db.Text)
    base_dcprovider = db.Column(db.Text)

    error = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        super(NonDoiProduct, self).__init__(**kwargs)

    def set_data_from_hybrid(self, high_priority=False):
        return

    @property
    def first_author_family_name(self):
        first_author = None
        if self.authors:
            try:
                first_author = self.authors.split(u",")[0]
            except UnicodeEncodeError:
                print u"unicode error on", self.authors
        return first_author

    def look_up_doi_from_biblio(self):
        if self.title and self.first_author_family_name:
            # print u"self.first_author_family_name", self.first_author_family_name
            url_template = u"""http://doi.crossref.org/servlet/query?pid=team@impactstory.org&qdata= <?xml version="1.0"?> <query_batch version="2.0" xsi:schemaLocation="http://www.crossref.org/qschema/2.0 http://www.crossref.org/qschema/crossref_query_input2.0.xsd" xmlns="http://www.crossref.org/qschema/2.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"> <head> <email_address>support@crossref.org</email_address><doi_batch_id>ABC_123_fff </doi_batch_id> </head> <body> <query enable-multiple-hits="true" secondary-query="author-title-multiple-hits">   <article_title match="exact">{title}</article_title>    <author search-all-authors="true" match="exact">{first_author}</author> </query> </body></query_batch>"""
            url = url_template.format(
                title = self.title,
                first_author = self.first_author_family_name
            )
            try:
                r = requests.get(url, timeout=5)
                if r.status_code==200 and r.text and u"|" in r.text:
                    doi = r.text.rsplit(u"|", 1)[1]
                    if doi and doi.startswith(u"10."):
                        doi = doi.strip()
                        print u"got a doi! {}".format(self.doi)
                        return doi
            except requests.Timeout:
                print "timeout"

        # print ".",
        return None



    def set_biblio_from_orcid(self):
        if not self.orcid_api_raw_json:
            print u"no self.orcid_api_raw_json for non_doi_product {}".format(self.id)
        set_biblio_from_biblio_dict(self, self.orcid_api_raw_json)

    @property
    def display_authors(self):
        return self.authors_short


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
            "_title": self.display_title,  # duplicate just for api reading help
            "title": self.display_title,
            # "title_normalized": normalize(self.display_title),
            "journal": self.journal,
            "authors": self.display_authors,
            "altmetric_id": None,
            "altmetric_score": None,
            "num_posts": 0,
            "is_oa_journal": False,
            "is_oa_repository": self.is_open,
            "is_open": False,
            "is_open_new": self.is_open,
            "open_url": self.open_url,
            "open_urls": self.open_urls,
            "sources": [],
            "posts": [],
            "events_last_week_count": 0,
            "genre": self.guess_genre()
        }





