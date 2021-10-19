import datetime
import hashlib
import uuid
from urllib.parse import quote, urlparse

import shortuuid

from app import db
from app import logger
from recordthresher.pmh_record_record import PmhRecordRecord
from recordthresher.util import normalize_author
from .record_maker import RecordMaker


class PmhRecordMaker(RecordMaker):
    @classmethod
    def make_record(cls, pmh_record):
        return cls._dispatch(pmh_record=pmh_record)

    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return False

    @staticmethod
    def is_high_quality(pmh_record):
        prefixes = [
            'oai:HAL:hal-',
            'oai:arXiv.org:'
        ]

        if pmh_record.pmh_id and any(pmh_record.pmh_id.startswith(prefix) for prefix in prefixes):
            return True

        return False

    @staticmethod
    def _parseland_api_url(repo_page):
        return f'https://parseland.herokuapp.com/parse-repository?page-id={repo_page.id}'

    @classmethod
    def _make_record_impl(cls, pmh_record):
        if not PmhRecordMaker.is_high_quality(pmh_record):
            logger.info(f'not making a recordthresher record for {pmh_record}')
            return None

        if not (pmh_record and pmh_record.id):
            return None

        best_page = cls._best_page(pmh_record)
        if not best_page:
            logger.info(f'cannot pick a best repo page for {pmh_record} so not making a record')
            return None

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'pmh_record:{pmh_record.id}'.encode('utf-8')).digest()[0:16])
        )

        record = PmhRecordRecord.query.get(record_id)

        if not record:
            record = PmhRecordRecord(id=record_id)

        record.pmh_id = pmh_record.id
        record.repository_id = pmh_record.endpoint_id

        record.title = pmh_record.title

        authors = [
            normalize_author({"raw": author}) for author in pmh_record.authors
        ] if pmh_record.authors else []

        record.set_jsonb('authors', authors)

        record.set_jsonb('citations', [])

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

        cls._make_source_specific_record_changes(record, pmh_record, best_page)

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        return record

    @staticmethod
    def _best_page(pmh_record):
        def repo_host_match_score(score_page):
            repo_host = None
            page_host = urlparse(score_page.url).hostname

            if score_page.endpoint and score_page.endpoint.pmh_url:
                repo_host = urlparse(score_page.endpoint.pmh_url).hostname

            if not repo_host or not page_host:
                return 0

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

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, best_page):
        pass
