from sqlalchemy.dialects.postgresql import JSONB

from app import db


class DataCiteRaw(db.Model):
    __tablename__ = 'datacite'
    __table_args__ = {'schema': 'recordthresher'}

    id = db.Column(db.Text, primary_key=True)
    title = db.Column(db.Text)
    datacite_api_raw = db.Column(JSONB)
    created_date = db.Column(db.DateTime, server_default=db.func.now())
    updated_date = db.Column(db.DateTime, onupdate=db.func.now())
