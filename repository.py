import os
import re
from sickle import Sickle
from sickle.response import OAIResponse
from sickle.iterator import OAIItemIterator
from sickle.models import ResumptionToken
from sickle.oaiexceptions import NoRecordsMatch
import requests
from time import sleep
from time import time
import datetime
import shortuuid
from random import random
import argparse
import lxml
from sqlalchemy import or_
from sqlalchemy import and_
import hashlib
import json

from app import db
from app import logger
import pmh_record

import pub
from util import elapsed
from util import safe_commit

def get_repos_by_ids(ids):
    repos = db.session.query(Repository).filter(Repository.id.in_(ids)).all()
    return repos

def get_sources_data(query_string=None):
    response = get_repository_data(query_string) + get_journal_data(query_string)
    return response

def get_sources_data_fast():
    all_journals = JournalMetadata.query.all()
    all_repos = Repository.query.all()
    all_sources = all_journals + all_repos

    return all_sources

    # all_sources_dict = {}
    # for source in all_sources:
    #     all_sources_dict[source.dedup_name] = source
    #
    # return all_sources_dict.values()


def get_journal_data(query_string=None):
    journal_meta_query = JournalMetadata.query
    if query_string:
        journal_meta_query = journal_meta_query.filter(or_(
            JournalMetadata.journal.ilike(u"%{}%".format(query_string)),
            JournalMetadata.publisher.ilike(u"%{}%".format(query_string)))
        )
    journal_meta = journal_meta_query.all()
    return journal_meta

def get_raw_repo_meta(query_string=None):
    raw_repo_meta_query = Repository.query.distinct(Repository.repository_name, Repository.institution_name)
    if query_string:
        raw_repo_meta_query = raw_repo_meta_query.filter(or_(
            Repository.repository_name.ilike(u"%{}%".format(query_string)),
            Repository.institution_name.ilike(u"%{}%".format(query_string)),
            Repository.home_page.ilike(u"%{}%".format(query_string)),
            Repository.id.ilike(u"%{}%".format(query_string))
        ))
    raw_repo_meta = raw_repo_meta_query.all()
    return raw_repo_meta

def get_repository_data(query_string=None):
    raw_repo_meta = get_raw_repo_meta(query_string)
    block_word_list = [
        "journal",
        "jurnal",
        "review",
        "revista",
        "annals",
        "annales",
        "magazine",
        "conference",
        "proceedings",
        "anales",
        "publisher",
        "press",
        "ojs",
        "bulletin",
        "acta"
    ]
    good_repo_meta = []
    for repo_meta in raw_repo_meta:
        if repo_meta.repository_name and repo_meta.institution_name:
            good_repo = True
            if repo_meta.bad_data:
                good_repo = False
            if repo_meta.is_journal:
                good_repo = False
            for block_word in block_word_list:
                if block_word in repo_meta.repository_name.lower() \
                        or block_word in repo_meta.institution_name.lower() \
                        or block_word in repo_meta.home_page.lower():
                    good_repo = False
                for endpoint in repo_meta.endpoints:
                    if endpoint.pmh_url and block_word in endpoint.pmh_url.lower():
                        good_repo = False
            if good_repo:
                good_repo_meta.append(repo_meta)
    return good_repo_meta


# created using this:
#     create table journal_metadata as (
#         select distinct on (normalize_title_v2(journal_name), normalize_title_v2(publisher))
#         journal_name as journal, publisher, journal_issns as issns from export_main_no_versions_20180116 where genre = 'journal-article')
# delete from journal_metadata where publisher='CrossRef Test Account'
class JournalMetadata(db.Model):
    publisher = db.Column(db.Text, primary_key=True)
    journal = db.Column(db.Text, primary_key=True)
    issns = db.Column(db.Text)

    @property
    def text_for_comparision(self):
        response = ""
        for attr in ["publisher", "journal"]:
            value = getattr(self, attr)
            if not value:
                value = ""
            response += value.lower()
        return response

    @property
    def dedup_name(self):
        return self.publisher.lower() + " " + self.journal.lower()

    @property
    def home_page(self):
        if self.issns:
            issn = self.issns.split(",")[0]
        else:
            issn = ""
        url = u"https://www.google.com/search?q={}+{}".format(self.journal, issn)
        url = url.replace(u" ", u"+")
        return url

    def to_csv_row(self):
        row = []
        for attr in ["home_page", "publisher", "journal"]:
            value = getattr(self, attr)
            if not value:
                value = ""
            value = value.replace(",", "; ")
            row.append(value)
        csv_row = u",".join(row)
        return csv_row

    def __repr__(self):
        return u"<JournalMetadata ({} {})>".format(self.journal, self.publisher)

    def to_dict(self):
        response = {
            "home_page": self.home_page,
            "institution_name": self.publisher,
            "repository_name": self.journal
        }
        return response



class Repository(db.Model):
    id = db.Column(db.Text, primary_key=True)
    home_page = db.Column(db.Text)
    institution_name = db.Column(db.Text)
    repository_name = db.Column(db.Text)
    error_raw = db.Column(db.Text)
    bad_data = db.Column(db.Text)
    is_journal = db.Column(db.Boolean)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        super(self.__class__, self).__init__(**kwargs)

    @property
    def text_for_comparision(self):
        return self.home_page.lower() + self.repository_name.lower() + self.institution_name.lower() + self.id.lower()

    @property
    def dedup_name(self):
        return self.institution_name.lower() + " " + self.repository_name.lower()

    def __repr__(self):
        return u"<Repository ({}) {}>".format(self.id, self.institution_name)

    def to_csv_row(self):
        row = []
        for attr in ["home_page", "institution_name", "repository_name"]:
            value = getattr(self, attr)
            if not value:
                value = ""
            value = value.replace(",", "; ")
            row.append(value)
        csv_row = u",".join(row)
        return csv_row

    def to_dict(self):
        response = {
            # "id": self.id,
            "home_page": self.home_page,
            "institution_name": self.institution_name,
            "repository_name": self.repository_name
            # "pmh_url": self.endpoint.pmh_url,
        }
        return response



