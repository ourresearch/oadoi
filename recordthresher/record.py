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

    @staticmethod
    def remove_json_keys(obj, keys):
        obj_copy = json.loads(json.dumps(obj))

        if isinstance(obj_copy, dict):
            for key in keys:
                try:
                    del obj_copy[key]
                except KeyError:
                    pass

            obj_keys = obj_copy.keys()
            for obj_key in obj_keys:
                if isinstance(obj_copy[obj_key], dict) or isinstance(obj_copy[obj_key], list):
                    obj_copy[obj_key] = Record.remove_json_keys(obj_copy[obj_key], keys)
        elif isinstance(obj_copy, list):
            for i in range(0, len(obj_copy)):
                if isinstance(obj_copy[i], dict) or isinstance(obj_copy[i], list):
                    obj_copy[i] = Record.remove_json_keys(obj_copy[i], keys)

        return obj_copy

    def set_jsonb(self, name, value):
        if name not in self._original_json:
            original_value = getattr(self, name)
            self._original_json[name] = json.dumps(original_value, sort_keys=True, indent=2)

        setattr(self, name, value)

    def flag_modified_jsonb(self, ignore_keys=None):
        ignore_keys = ignore_keys or {}

        for attribute_name in self._original_json:
            original_value = json.loads(self._original_json[attribute_name])
            current_value = getattr(self, attribute_name)

            if attribute_name in ignore_keys:
                original_value = Record.remove_json_keys(original_value, ignore_keys[attribute_name])
                current_value = Record.remove_json_keys(current_value, ignore_keys[attribute_name])

            original_json = json.dumps(original_value, sort_keys=True, indent=2)
            current_json = json.dumps(current_value, sort_keys=True, indent=2)

            if original_json != current_json:
                flag_modified(self, attribute_name)
