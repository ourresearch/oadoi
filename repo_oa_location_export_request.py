from app import db
from sqlalchemy.schema import FetchedValue
from sqlalchemy import or_, text


class RepoOALocationExportRequest(db.Model):
    id = db.Column(db.BigInteger, primary_key=True, server_default=FetchedValue())
    endpoint_id = db.Column(db.Text)
    requested = db.Column(db.DateTime)
    email = db.Column(db.Text)
    started = db.Column(db.DateTime)
    finished = db.Column(db.DateTime)
    success = db.Column(db.Boolean)
    tries = db.Column(db.Integer, nullable=False, server_default=text('0'))
    error = db.Column(db.Text)

    def __repr__(self):
        return f'<RepoOALocationExportRequest ({self.endpoint_id}, {self.requested}, {self.email})'
