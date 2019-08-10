from sqlalchemy.dialects.postgresql import JSONB

from app import db


class Journal(db.Model):
    issn_l = db.Column(db.Text, primary_key=True)
    issns = db.Column(JSONB)
    api_raw_crossref = db.Column(JSONB)
    api_raw_issn = db.Column(JSONB)

    def __repr__(self):
        return u'<Journal ({issn_l})>'.format(
            issn_l=self.issn_l
        )