from sqlalchemy.dialects.postgresql import JSONB

from app import db
from recordthresher.record import Record


class PmhRecordRecord(Record):
    __tablename__ = None

    pmh_id = db.Column(db.Text)
    repository_id = db.Column(db.Text)
    unpaywall_api_response = db.Column(JSONB)

    __mapper_args__ = {
        "polymorphic_identity": "pmh_record"
    }
