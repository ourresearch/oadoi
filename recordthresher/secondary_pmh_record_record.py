from recordthresher.record import Record


class SecondaryPmhRecordRecord(Record):
    __tablename__ = None

    __mapper_args__ = {
        "polymorphic_identity": "secondary_pmh_record"
    }
