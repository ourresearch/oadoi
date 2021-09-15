import datetime
from urllib.parse import quote

from app import db
from works_db.location import Location


class CrossrefDoiLocation(Location):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'crossref_doi'}

    @staticmethod
    def from_pub(pub):
        location = CrossrefDoiLocation.query.filter(CrossrefDoiLocation.doi == pub.id).scalar()

        if not location:
            location = CrossrefDoiLocation()

        pub.recalculate()

        location.title = pub.title
        location.authors = pub.authors
        location.doi = pub.id

        location.record_webpage_url = pub.url

        if pub.landing_page_is_archived():
            location.record_webpage_archive_url = pub.landing_page_archive_url()
        else:
            location.record_webpage_archive_url = None

        location.record_structured_url = f'https://api.crossref.org/v1/works/http://dx.doi.org/{quote(pub.id)}'
        location.record_structured_archive_url = None

        if pub.best_oa_location.metadata_url == pub.url:
            location.work_pdf_url = pub.best_oa_location.pdf_url
            location.is_work_pdf_url_free_to_read = pub.best_oa_location.pdf_url and True
            location.is_oa = pub.best_oa_location is not None
            location.oa_date = pub.best_oa_location.oa_date
            location.open_license = pub.best_oa_location.license
            location.open_version = pub.best_oa_location.version
        else:
            location.work_pdf_url = None
            location.is_work_pdf_url_free_to_read = None
            location.is_work_pdf_url_free_to_read = False
            location.is_oa = False
            location.oa_date = None
            location.open_license = None
            location.open_version = None

        if db.session.is_modified(location):
            location.updated = datetime.datetime.utcnow().isoformat()

        return location
