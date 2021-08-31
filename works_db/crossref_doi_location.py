from works_db.location import Location
from app import db


class CrossrefDoiLocation(Location):
    __mapper_args__ = {'polymorphic_identity': 'crossref_doi'}