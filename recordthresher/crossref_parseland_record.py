from recordthresher.record import Record


class CrossrefParselandRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'crossref_parseland'}