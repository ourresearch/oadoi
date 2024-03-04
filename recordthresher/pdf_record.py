from recordthresher.record import Record


class PDFRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'crossref_pdf'}