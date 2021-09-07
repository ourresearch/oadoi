import datetime
import random

import shortuuid
from sqlalchemy import or_
from sqlalchemy import sql
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from page import PageBase


class RepoPage(PageBase):
    repo_id = db.Column(db.Text)  # delete once endpoint_id is populated
    doi = db.Column(db.Text, db.ForeignKey("pub.id"))
    authors = db.Column(JSONB)

    num_pub_matches = db.Column(db.Numeric)
    match_type = db.Column(db.Text)

    match_title = db.Column(db.Boolean)
    match_doi = db.Column(db.Boolean)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:20]
        self.error = ""
        self.rand = random.random()
        self.updated = datetime.datetime.utcnow().isoformat()
        super(RepoPage, self).__init__(**kwargs)

    def scrape_if_matches_pub(self):
        self.num_pub_matches = self.query_for_num_pub_matches()

        if self.num_pub_matches > 0 and self.scrape_eligible():
            return self.scrape()

    def enqueue_scrape_if_matches_pub(self):
        pass
        # self.num_pub_matches = self.query_for_num_pub_matches()
        #
        # if self.num_pub_matches > 0 and self.scrape_eligible():
        #     stmt = sql.text(
        #         'insert into page_green_scrape_queue (id, finished, endpoint_id) values (:id, :finished, :endpoint_id) on conflict do nothing'
        #     ).bindparams(id=self.id, finished=self.scrape_updated, endpoint_id=self.endpoint_id)
        #     db.session.execute(stmt)

    def __repr__(self):
        return "<PageNew ( {} ) {}>".format(self.pmh_id, self.url)

    def to_dict(self, include_id=True):
        response = {
            "oaipmh_id": self.pmh_record and self.pmh_record.bare_pmh_id,
            "oaipmh_record_timestamp": self.record_timestamp.isoformat(),
            "pdf_url": self.scrape_pdf_url,
            "title": self.title,
            "version": self.scrape_version,
            "license": self.scrape_license,
            "oaipmh_api_url": self.get_pmh_record_url()
        }
        if include_id:
            response["id"] = self.id
        return response

    def query_for_num_pub_matches(self):
        from pmh_record import title_is_too_common
        from pmh_record import title_is_too_short
        from pub import Pub

        if self.match_title and not (
            title_is_too_common(self.normalized_title)
            or title_is_too_short(self.normalized_title)
        ):
            title_match_clause = Pub.normalized_title == self.normalized_title
        else:
            title_match_clause = None

        if self.match_doi and self.doi:
            doi_match_clause = Pub.id == self.doi
        else:
            doi_match_clause = None

        if doi_match_clause is not None and title_match_clause is not None:
            match_clause = or_(title_match_clause, doi_match_clause)
        elif title_match_clause is not None:
            match_clause = title_match_clause
        elif doi_match_clause is not None:
            match_clause = doi_match_clause
        else:
            match_clause = None

        if match_clause is not None:
            return db.session.query(Pub.id).filter(match_clause).count()
        else:
            return 0
