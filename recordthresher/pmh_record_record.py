import datetime
import hashlib
import uuid
from urllib.parse import quote, urlparse

import shortuuid

from app import db
from recordthresher.record import Record


class PmhRecordRecord(Record):
    __tablename__ = None

    pmh_id = db.Column(db.Text)
    repository_id = db.Column(db.Text)

    __mapper_args__ = {
        "polymorphic_identity": "pmh_record"
    }

    @staticmethod
    def from_pmh_record(pmh_record):
        if not (pmh_record and pmh_record.id):
            return None

        best_page = PmhRecordRecord.best_page(pmh_record)
        if not best_page:
            return None

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(pmh_record.id.encode('utf-8')).digest()[0:16])
        )

        record = PmhRecordRecord.query.get(record_id)

        if not record:
            record = PmhRecordRecord(id=record_id)

        record.pmh_id = pmh_record.id
        record.repository_id = pmh_record.endpoint_id

        record.title = pmh_record.title

        record.authors = [
            PmhRecordRecord.normalize_author({"raw": author}) for author in pmh_record.authors
        ] if pmh_record.authors else []

        record.doi = pmh_record.doi

        if best_page.landing_page_archive_url():
            record.record_webpage_url = best_page.url
        else:
            record.record_webpage_url = None

        record.record_webpage_archive_url = best_page.landing_page_archive_url()
        record.record_structured_url = best_page.get_pmh_record_url()
        record.record_structured_archive_url = f'https://api.unpaywall.org/pmh_record_xml/{quote(pmh_record.id)}'

        record.work_pdf_url = best_page.scrape_pdf_url
        record.work_pdf_archive_url = best_page.fulltext_pdf_archive_url()
        record.is_work_pdf_url_free_to_read = True if best_page.scrape_pdf_url else None

        record.is_oa = bool(best_page.is_open)

        if record.is_oa:
            best_page_first_available = best_page.first_available
            if isinstance(best_page_first_available, datetime.date):
                record.oa_date = datetime.datetime.combine(
                    best_page_first_available,
                    datetime.datetime.min.time()
                )
            else:
                record.oa_date = best_page_first_available

            record.open_license = best_page.scrape_license
            record.open_version = best_page.scrape_version
        else:
            record.oa_date = None
            record.open_license = None
            record.open_version = None

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        return record

    @staticmethod
    def best_page(pmh_record):
        def repo_host_match_score(score_page):
            repo_host = None
            if score_page.endpoint and score_page.endpoint.pmh_url:
                repo_host = urlparse(score_page.endpoint.pmh_url).hostname

            if not repo_host:
                return 0

            page_host = urlparse(score_page.url).hostname
            page_host_parts = list(reversed(page_host.split('.')))
            repo_host_parts = list(reversed(repo_host.split('.')))

            match_score = 0
            for i in range(0, min(len(page_host_parts), len(repo_host_parts))):
                if repo_host_parts[i] == page_host_parts[i]:
                    match_score += 1

            return match_score

        ranked_pages = sorted(
            pmh_record.pages,
            key=lambda page: (
                page.scrape_metadata_url is not None,
                page.scrape_pdf_url is not None,
                page.scrape_metadata_url != page.scrape_pdf_url,
                repo_host_match_score(page)
            )
        )

        return ranked_pages[-1]
