from app import db
from recordthresher.record import Record


class PmhRecordRecord(Record):
    __tablename__ = None

    pmh_id = db.Column(db.Text)
    repository_id = db.Column(db.Text)

    __mapper_args__ = {
        "polymorphic_identity": "pmh_record"
    }
