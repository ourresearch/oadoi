from datetime import datetime
from app import db

class OpenAlexRecordTrack(db.Model):
    __table_args__ = {"schema": "logs"}
    __tablename__ = "recordtrack_record"
    __bind_key__ = 'openalex'

    id = db.Column(db.BigInteger, primary_key=True)
    doi = db.Column(db.Text)
    work_id = db.Column(db.BigInteger)
    arxiv_id = db.Column(db.Text)
    pmid = db.Column(db.BigInteger)
    pmh_id = db.Column(db.Text)
    created_at = db.Column(db.DateTime)
    last_tracked_at = db.Column(db.DateTime)
    work_id_found = db.Column(db.DateTime)
    api_found = db.Column(db.DateTime)
    note = db.Column(db.Text)
    active = db.Column(db.Boolean)
    origin = db.Column(db.Text)
    origin_timestamp = db.Column(db.DateTime)
    first_tracked_at = db.Column(db.DateTime)
