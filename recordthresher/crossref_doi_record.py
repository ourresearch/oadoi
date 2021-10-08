import datetime
import hashlib
import uuid
from urllib.parse import quote

import shortuuid

from app import db
from recordthresher.record import Record


class CrossrefDoiRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'crossref_doi'}

    @staticmethod
    def from_pub(pub):
        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'crossref_doi:{pub.id}'.encode('utf-8')).digest()[0:16])
        )

        record = CrossrefDoiRecord.query.get(record_id)

        if not record:
            record = CrossrefDoiRecord(id=record_id)

        record.title = pub.title
        authors = [CrossrefDoiRecord.normalize_author(author) for author in pub.authors] if pub.authors else []
        record.set_jsonb('authors', authors)

        record.doi = pub.id
        record.abstract = pub.abstract_from_crossref or None
        record.published_date = pub.issued

        citations = [
            CrossrefDoiRecord.normalize_citation(ref)
            for ref in pub.crossref_api_raw_new.get('reference', [])
        ]
        record.set_jsonb('citations', citations)

        record.record_webpage_url = pub.url
        record.journal_issn_l = pub.issn_l
        record.journal_id = pub.journalsdb_journal_id

        record.record_webpage_archive_url = pub.landing_page_archive_url() if pub.doi_landing_page_is_archived else None

        record.record_structured_url = f'https://api.crossref.org/v1/works/{quote(pub.id)}'
        record.record_structured_archive_url = f'https://api.unpaywall.org/crossref_api_cache/{quote(pub.id)}'

        if pub.best_oa_location and pub.best_oa_location.metadata_url == pub.url:
            record.work_pdf_url = pub.best_oa_location.pdf_url
            record.is_work_pdf_url_free_to_read = True if pub.best_oa_location.pdf_url else None
            record.is_oa = pub.best_oa_location is not None

            if isinstance(pub.best_oa_location.oa_date, datetime.date):
                record.oa_date = datetime.datetime.combine(
                    pub.best_oa_location.oa_date,
                    datetime.datetime.min.time()
                )
            else:
                record.oa_date = pub.best_oa_location.oa_date

            record.open_license = pub.best_oa_location.license
            record.open_version = pub.best_oa_location.version
        else:
            record.work_pdf_url = None
            record.is_work_pdf_url_free_to_read = None
            record.is_work_pdf_url_free_to_read = None
            record.is_oa = False
            record.oa_date = None
            record.open_license = None
            record.open_version = None

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        return record
