import re

import shortuuid
from sqlalchemy import or_
from sqlalchemy.orm import defer

from app import db
from journal import Journal


def get_repos_by_ids(ids):
    repos = db.session.query(Repository).filter(Repository.id.in_(ids)).all()
    return repos


def get_sources_data(query_string=None):
    response = get_repository_data(query_string) + get_journal_data(query_string)
    return response


def get_sources_data_fast():
    all_journals = Journal.query.options(defer('api_raw_crossref'), defer('api_raw_issn')).all()
    all_repos = Repository.query.all()
    all_sources = all_journals + all_repos

    return all_sources


def get_journal_data(query_string=None):
    journal_meta_query = Journal.query.options(defer('api_raw_crossref'), defer('api_raw_issn'))
    if query_string:
        journal_meta_query = journal_meta_query.filter(or_(
            Journal.title.ilike("%{}%".format(query_string)),
            Journal.publisher.ilike("%{}%".format(query_string)))
        )
    journal_meta = journal_meta_query.all()
    return journal_meta


def get_raw_repo_meta(query_string=None):
    raw_repo_meta_query = Repository.query.distinct(Repository.repository_name, Repository.institution_name)
    if query_string:
        raw_repo_meta_query = raw_repo_meta_query.filter(or_(
            Repository.repository_name.ilike("%{}%".format(query_string)),
            Repository.institution_name.ilike("%{}%".format(query_string)),
            Repository.home_page.ilike("%{}%".format(query_string)),
            Repository.id.ilike("%{}%".format(query_string))
        ))
    raw_repo_meta = raw_repo_meta_query.all()
    return raw_repo_meta


def get_repository_data(query_string=None):
    raw_repo_meta = get_raw_repo_meta(query_string)
    block_word_list = [
        "journal",
        "journals",
        "jurnal",
        "review",
        "revista",
        "revistas",
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
    repo_name_whitelist = [
        "journal of geophysics"
    ]
    good_repo_meta = []
    for repo_meta in raw_repo_meta:
        if repo_meta.repository_name and repo_meta.institution_name:
            good_repo = True
            if repo_meta.bad_data:
                good_repo = False
            if repo_meta.is_journal:
                good_repo = False
            if repo_meta.repository_name.lower() not in repo_name_whitelist:
                for block_word in block_word_list:
                    block_pattern = re.compile(r'\b{}\b'.format(block_word))
                    if block_pattern.search(repo_meta.repository_name.lower()) \
                            or block_pattern.search(repo_meta.institution_name.lower()) \
                            or block_pattern.search((repo_meta.home_page or '').lower()):
                        good_repo = False
                    for endpoint in repo_meta.endpoints:
                        if endpoint.pmh_url and block_pattern.search(endpoint.pmh_url.lower()):
                            good_repo = False
            if good_repo:
                good_repo_meta.append(repo_meta)
    return good_repo_meta


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

    def display_name(self):
        return ' - '.join(
            [_f for _f in [(s or '').strip() for s in [self.institution_name, self.repository_name]] if _f]
        ) or None

    def __repr__(self):
        return "<Repository ({}) {}>".format(self.id, self.institution_name)

    def to_csv_row(self):
        row = []
        for attr in ["home_page", "institution_name", "repository_name"]:
            value = getattr(self, attr) or ''
            value = value.replace(',', '; ')
            row.append(value)
        csv_row = ','.join(row)
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



