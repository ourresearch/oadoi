import json

from app import db


class WunpaywallPub(db.Model):
    __tablename__ = 'unpaywall_from_walden'
    __table_args__ = {'schema': 'unpaywall'}
    __bind_key__ = 'openalex'

    doi = db.Column(db.String, primary_key=True)
    json_response = db.Column(db.Text)

    def to_dict(self):
        return json.loads(self.json_response)
