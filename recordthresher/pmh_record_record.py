from app import db
from recordthresher.record import Record


class PmhRecordRecord(Record):
    __tablename__ = None

    __mapper_args__ = {
        "polymorphic_identity": "pmh_record"
    }
