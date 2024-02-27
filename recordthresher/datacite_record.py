from recordthresher.record import Record


class DataCiteRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'datacite_record'}
