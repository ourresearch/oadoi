import datetime
import json

import dateutil.parser
import shortuuid
from sqlalchemy import orm
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
    published_date = db.Column(db.Date)
    genre = db.Column(db.Text)
    doi = db.Column(db.Text)
    abstract = db.Column(db.Text)
    citations = db.Column(JSONB)
    mesh = db.Column(JSONB)
    is_retracted = db.Column(db.Boolean)

    journal_id = db.Column(db.Text)
    journal_issn_l = db.Column(db.Text)
    publisher = db.Column(db.Text)

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

        self._original_json = {}
        super(Record, self).__init__(**kwargs)

    @orm.reconstructor
    def init_on_load(self):
        self._original_json = {}

    __mapper_args__ = {'polymorphic_on': record_type}

    def __repr__(self):
        return "<Record ( {} ) {}, {}, {}>".format(self.id, self.record_type, self.doi, self.title)

    def set_authors(self, authors):
        self.set_jsonb('authors', authors)

    def _set_date(self, name, value):
        if isinstance(value, str):
            default_datetime = datetime.datetime(datetime.MAXYEAR, 1, 1)
            parsed_value = dateutil.parser.parse(value, default=default_datetime)
            if parsed_value.year == datetime.MAXYEAR and str(datetime.MAXYEAR) not in value:
                value = None
            else:
                value = parsed_value.date()
        elif isinstance(value, datetime.datetime):
            value = value.date()

        setattr(self, name, value)

    def set_published_date(self, published_date):
        self._set_date('published_date', published_date)

    def set_jsonb(self, name, value):
        if name not in self._original_json:
            self._original_json[name] = json.dumps(getattr(self, name), sort_keys=True, indent=2)

        new_json = json.dumps(value, sort_keys=True, indent=2)
        setattr(self, name, value)

        if self._original_json.get(name, '') != new_json:
            flag_modified(self, name)
