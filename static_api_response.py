from sqlalchemy.dialects.postgresql import JSONB

from app import db


class StaticAPIResponse(db.Model):
    id = db.Column(db.Text, primary_key=True)
    response_jsonb = db.Column(JSONB)

    def __repr__(self):
        return f'<StaticAPIResponse ({self.id})'
