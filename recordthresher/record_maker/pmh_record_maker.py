import datetime
import hashlib
import json
import re
import uuid
from urllib.parse import quote

import shortuuid

from app import db
from app import logger
from recordthresher.pmh_record_record import PmhRecordRecord
from recordthresher.record_unpaywall_response import RecordUnpaywallResponse
from recordthresher.util import ARXIV_ID_PATTERN
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
            'oai:arXiv.org:',
            'oai:doaj.org/article:',
            'cdr.lib.unc.edu:',
            'oai:deepblue.lib.umich.edu:',
            'oai:osti.gov:',
            'oai:zenodo.org:',
            'oai:RePEc:',
            'oai:dergipark.org.tr:',
        ]

        if pmh_record and pmh_record.pmh_id and any(pmh_record.pmh_id.startswith(prefix) for prefix in prefixes):
            return True

        return False

    @staticmethod
    def _parseland_api_url(repo_page):
        return f'https://parseland.herokuapp.com/parse-repository?page-id={repo_page.id}'

    @classmethod
    def _make_record_impl(cls, pmh_record):
        if not (pmh_record and pmh_record.id):
            return None

        if not PmhRecordMaker.is_high_quality(pmh_record):
            logger.info(f'not making a recordthresher record for {pmh_record}')
            return None

        if best_page := cls._representative_page(pmh_record):
            logger.info(f'selected the representative page {best_page}')
        else:
            logger.info(f'cannot pick a representative repo page for {pmh_record} so not making a record')
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

        if not record.published_date:
            logger.info(f'no published date determined for {pmh_record} so not making a record')
            return None

        return record

    @classmethod
    def make_unpaywall_api_response(cls, record):
        unpaywall_api_response = RecordUnpaywallResponse.query.get(record.id)
        if not unpaywall_api_response:
            unpaywall_api_response = RecordUnpaywallResponse(
                recordthresher_id=record.id,
                updated=datetime.datetime.utcnow(),
                last_changed_date=datetime.datetime.utcnow()
            )

        old_response_jsonb = unpaywall_api_response.response_jsonb or {}

        response_pub = None

        if record.doi:
            from pub import Pub
            response_pub = Pub.query.get(record.doi)

        if not response_pub:
            from recordthresher.recordthresher_pub import RecordthresherPub
            response_pub = RecordthresherPub(id='', title=record.title)
            response_pub.normalized_title = record.normalized_title
            response_pub.authors = json.loads(record.authors)
            response_pub.response_jsonb = unpaywall_api_response.response_jsonb
            db.session().enable_relationship_loading(response_pub)

        response_pub.recalculate()
        response_pub.set_results()

        response_pub.updated = unpaywall_api_response.updated
        response_pub.last_changed_date = unpaywall_api_response.last_changed_date

        response_pub.decide_if_response_changed(old_response_jsonb)

        unpaywall_api_response.updated = response_pub.updated
        unpaywall_api_response.last_changed_date = response_pub.last_changed_date
        unpaywall_api_response.response_jsonb = response_pub.response_jsonb

        return unpaywall_api_response

    @classmethod
    def _representative_page(cls, pmh_record):
        return None

    @classmethod
    def _make_source_specific_record_changes(cls, record, pmh_record, best_page):
        pass

    @classmethod
    def _set_arxiv_id(cls, record, pmh_xml_tree):
        for identifier in pmh_xml_tree.findall('.//identifier'):
            if identifier.text and (match := re.search('ARXIV:(.*)', identifier.text)):
                record.arxiv_id = 'arXiv:' + match[1].strip()
                return

        for relation in pmh_xml_tree.findall('.//relation'):
            if relation.text and (match := re.search(fr'altIdentifier/.*({ARXIV_ID_PATTERN})', relation.text)):
                record.arxiv_id = match[1]
                return

    @classmethod
    def _set_pmc_id(cls, record, pmh_xml_tree):
        for identifier in pmh_xml_tree.findall('.//identifier'):
            if identifier.text and (match := re.search('PUBMEDCENTRAL:(.*)', identifier.text)):
                record.pmcid = match[1].strip().lower()
                return

    @staticmethod
    def representative_page(pmh_record):
        for subcls in PmhRecordMaker.__subclasses__():
            if subcls._is_specialized_record_maker(pmh_record):
                if rp := subcls._representative_page(pmh_record):
                    return rp

        return None
