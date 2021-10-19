from recordthresher.record import Record


class CrossrefDoiRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'crossref_doi'}
