from sqlalchemy.dialects.postgresql import JSONB

from app import db


class RecordUnpaywallResponse(db.Model):
    __tablename__ = 'unpaywall_api_response'
    __table_args__ = {'schema': 'recordthresher'}

    recordthresher_id = db.Column(db.Text, primary_key=True)
    response_jsonb = db.Column(JSONB)
    updated = db.Column(db.DateTime)
    last_changed_date = db.Column(db.DateTime)
