import datetime
import hashlib
import json
import re
import shortuuid
import uuid
from urllib.parse import quote

from app import db, logger

from recordthresher.secondary_pmh_record_record import SecondaryPmhRecordRecord
from recordthresher.record_maker.pmh_record_maker import PmhRecordMaker
from recordthresher.util import normalize_author

class SecondaryPmhRecordMaker(PmhRecordMaker):
    @classmethod
    def _representative_page(cls, pmh_record):
        for repo_page in pmh_record.pages:
            if repo_page.scrape_version == 'publishedVersion':
                return repo_page
            elif repo_page.scrape_version == 'acceptedVersion':
                return repo_page
            elif repo_page.scrape_version is not None and repo_page.scrape_version != '':
                return repo_page

        return None

    @classmethod
    def _record_id(cls, pmh_record):
        return shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'secondary_pmh_record:{pmh_record.id}'.encode('utf-8')).digest()[0:16])
        )

    @classmethod
    def _existing_record_search(cls, record_id):
        return SecondaryPmhRecordRecord.query.get(record_id)

    @classmethod
    def _new_record_init(cls, record_id):
        return SecondaryPmhRecordRecord(id=record_id)

    @classmethod
    def _make_record_impl(cls, pmh_record):
        if not (pmh_record and pmh_record.id):
            return None

        if best_page := cls._representative_page(pmh_record):
            logger.info(f'selected the representative page {best_page}')
        else:
            logger.info(f'cannot pick a representative repo page for {pmh_record} so not making a record')
            return None

        record_id = cls._record_id(pmh_record)

        record = cls._existing_record_search(record_id)

        if not record:
            record = cls._new_record_init(record_id)

        record.pmh_id = pmh_record.id
        record.repository_id = pmh_record.endpoint_id

        record.title = pmh_record.title
        record.normalized_title = pmh_record.calc_normalized_title()

        authors = [
            normalize_author({"raw": author}) for author in pmh_record.authors
        ] if pmh_record.authors else []

        record.authors = authors

        record.citations = []

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

        if record.work_pdf_url is None and record.record_webpage_url is None:
            record.record_webpage_url = best_page.url

        record.is_oa = bool(best_page.is_open)
        record.open_license = best_page.scrape_license
        record.open_version = best_page.scrape_version

        cls._make_source_specific_record_changes(record, pmh_record, best_page)

        record.flag_modified_jsonb()

        record.authors = json.dumps(record.authors)
        record.citations = json.dumps(record.citations)

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        return record

