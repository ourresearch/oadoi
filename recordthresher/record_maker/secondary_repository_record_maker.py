import datetime
import hashlib
import uuid

import shortuuid

from app import db
from recordthresher.secondary_pmh_record_record import SecondaryPmhRecordRecord
from .record_maker import RecordMaker


class SecondaryRepositoryRecordMaker(RecordMaker):
    @classmethod
    def make_record(cls, pmh_record):
        return cls._dispatch(pmh_record=pmh_record)

    @staticmethod
    def _is_specialized_record_maker(pmh_record):
        return False

    @classmethod
    def _make_record_impl(cls, pub_open_location, work_title, work_normalized_title):
        if not (pub_open_location and pub_open_location.best_url):
            return None

        if not (
            pub_open_location.host_type == "repository"
            and pub_open_location.endpoint_id
            and pub_open_location.pmh_id
        ):
            return None

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'secondary_pmh_record:{pub_open_location.best_url}'.encode('utf-8')).digest()[0:16])
        )

        record = SecondaryPmhRecordRecord.query.get(record_id)

        if not record:
            record = SecondaryPmhRecordRecord(id=record_id)

        record.pmh_id = f"{pub_open_location.endpoint_id}:{pub_open_location.pmh_id}"
        record.repository_id = pub_open_location.endpoint_id

        record.title = work_title
        record.normalized_title = work_normalized_title

        record.doi = (
            pub_open_location.metadata_url
            and pub_open_location.metadata_url.startswith('https://doi.org/')
            and pub_open_location.metadata_url.replace('https://doi.org/', '')
        ) or None

        record.record_webpage_url = pub_open_location.metadata_url or None
        record.work_pdf_url = pub_open_location.pdf_url or None

        if not pub_open_location.pdf_url:
            record.is_work_pdf_url_free_to_read = None
        else:
            record.is_work_pdf_url_free_to_read = pub_open_location.best_url == pub_open_location.pdf_url

        record.is_oa = True
        record.open_license = pub_open_location.license
        record.open_version = pub_open_location.version
        record.work_id = -1

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        return record

