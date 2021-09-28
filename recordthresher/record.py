import datetime
import json
import re
from copy import deepcopy

import shortuuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.attributes import flag_modified

from app import db


class Record(db.Model):
    __tablename__ = 'record'
    __table_args__ = {'schema': 'recordthresher'}

    id = db.Column(db.Text, primary_key=True)
    record_type = db.Column(db.Text, nullable=False)
    updated = db.Column(db.DateTime)

    title = db.Column(db.Text)
    authors = db.Column(JSONB)
    published_date = db.Column(db.DateTime)
    genre = db.Column(db.Text)
    doi = db.Column(db.Text)

    citations = db.Column(JSONB)

    journal_id = db.Column(db.Text)
    journal_issn_l = db.Column(db.Text)

    record_webpage_url = db.Column(db.Text)
    record_webpage_archive_url = db.Column(db.Text)
    record_structured_url = db.Column(db.Text)
    record_structured_archive_url = db.Column(db.Text)

    work_pdf_url = db.Column(db.Text)
    work_pdf_archive_url = db.Column(db.Text)
    is_work_pdf_url_free_to_read = db.Column(db.Boolean)

    is_oa = db.Column(db.Boolean)
    oa_date = db.Column(db.DateTime)
    open_license = db.Column(db.Text)
    open_version = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:20]
        self.error = ""
        self.updated = datetime.datetime.utcnow().isoformat()
        super(Record, self).__init__(**kwargs)

    __mapper_args__ = {'polymorphic_on': record_type}

    def __repr__(self):
        return "<Record ( {} ) {}, {}, {}>".format(self.id, self.record_type, self.doi, self.title)

    def set_jsonb(self, name, value):
        old_json = json.dumps(getattr(self, name), sort_keys=True, indent=2)
        new_json = json.dumps(value, sort_keys=True, indent=2)

        setattr(self, name, value)

        if old_json != new_json:
            flag_modified(self, name)

    @staticmethod
    def normalize_author(author):
        # https://api.crossref.org/swagger-ui/index.html#model-Author
        author = deepcopy(author)

        for k in list(author.keys()):
            if k != k.lower():
                author[k.lower()] = author[k]
                del author[k]

        author.setdefault('raw', None)
        author.setdefault('affiliation', [])
        for affiliation in author['affiliation']:
            affiliation.setdefault('name', None)
        author.setdefault('sequence', None)
        author.setdefault('name', None)
        author.setdefault('family', None)
        author.setdefault('orcid', None)
        author.setdefault('suffix', None)
        author.setdefault('authenticated-orcid', None)
        author.setdefault('given', None)

        if author['orcid']:
            author['orcid'] = re.sub(r'.*((?:[0-9]{4}-){3}[0-9]{3}[0-9X]).*', r'\1', author['orcid'].upper())

        return author

    @staticmethod
    def normalize_citation(citation):
        citation = deepcopy(citation)

        # https://api.crossref.org/swagger-ui/index.html#model-Reference

        for k in list(citation.keys()):
            if k != k.lower():
                citation[k.lower()] = citation[k]
                del citation[k]

        citation.setdefault('raw', None)
        citation.setdefault('issn', None)
        citation.setdefault('standards-body', None)
        citation.setdefault('issue', None)
        citation.setdefault('key', None)
        citation.setdefault('series-title', None)
        citation.setdefault('isbn-type', None)
        citation.setdefault('doi-asserted-by', None)
        citation.setdefault('first-page', None)
        citation.setdefault('isbn', None)
        citation.setdefault('doi', None)
        citation.setdefault('component', None)
        citation.setdefault('article-title', None)
        citation.setdefault('volume-title', None)
        citation.setdefault('volume', None)
        citation.setdefault('author', None)
        citation.setdefault('standard-designator', None)
        citation.setdefault('year', None)
        citation.setdefault('unstructured', None)
        citation.setdefault('edition', None)
        citation.setdefault('journal-title', None)
        citation.setdefault('issn-type', None)

        return citation
