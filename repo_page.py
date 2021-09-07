from sqlalchemy import or_

from app import db
from page import PageNew


class RepoPage(PageNew):
    __tablename__ = None
    __mapper_args__ = {"polymorphic_identity": "any"}

    match_title = db.Column(db.Boolean)
    match_doi = db.Column(db.Boolean)

    def __init__(self, **kwargs):
        self.match_title = False
        self.match_title = False
        super(RepoPage, self).__init__(**kwargs)

    def scrape_if_matches_pub(self):
        pass

    def enqueue_scrape_if_matches_pub(self):
        pass

    def __repr__(self):
        return "<RepoPage ( {} ) {} match_title: {}, match_doi: {}>".format(
            self.pmh_id, self.url, self.match_title, self.match_doi
        )

    def to_dict(self, include_id=True):
        response = {
            "oaipmh_id": self.pmh_record and self.pmh_record.bare_pmh_id,
            "oaipmh_record_timestamp": self.record_timestamp.isoformat(),
            "pdf_url": self.scrape_pdf_url,
            "title": self.title,
            "version": self.scrape_version,
            "license": self.scrape_license,
            "oaipmh_api_url": self.get_pmh_record_url(),
            "match_title": self.match_title,
            "match_doi": self.match_doi
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
