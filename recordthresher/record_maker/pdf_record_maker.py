import datetime
import hashlib
import json
import os
import uuid

import shortuuid

from app import logger
from recordthresher.pdf_record import PDFRecord
from recordthresher.util import pdf_parser_response

PDF_PARSER_URL = os.getenv('OPENALEX_PDF_PARSER_URL')
PDF_PARSER_API_KEY = os.getenv('OPENALEX_PDF_PARSER_API_KEY')


def pdf_parse_api_url(pub):
    return f'{PDF_PARSER_URL}?doi={pub.id}&api_key={PDF_PARSER_API_KEY}&include_raw=false'


class PDFRecordMaker:

    @classmethod
    def new_id(cls, doi):
        return shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(
                f'parsed_pdf:{doi}'.encode('utf-8')).digest()[0:16])
        )

    @classmethod
    def make_record(cls, pub, update_existing=True):
        if not (pub and hasattr(pub, 'id') and pub.id):
            return None

        record_id = cls.new_id(pub.id)

        pdf_record = PDFRecord.query.get(record_id)

        if pdf_record and not update_existing:
            logger.info(
                f"not updating existing pdf record {pdf_record.id}")
            return None

        parsed_pdf_json = pdf_parser_response(pdf_parse_api_url(pub))
        if not parsed_pdf_json:
            return None
        return cls.make_pdf_record(pub.id,
                                   parsed_pdf_json,
                                   pdf_record)

    @classmethod
    def make_pdf_record(cls, doi, parsed_pdf_json, existing_record=None):
        if 'authors' in parsed_pdf_json:
            msg = parsed_pdf_json
        else:
            msg = parsed_pdf_json.get('message', {}) or {}

        has_data = any([bool(msg.get(key)) for key in msg.keys()])

        if not parsed_pdf_json:
            logger.info(
                f"didn't get a pdf parse response for {doi}, not making record")
            return None

        if not has_data:
            logger.info(f'grobid pdf data is empty for {doi}, not making record')
            return None

        authors = parsed_pdf_json.get('authors')
        references = parsed_pdf_json.get('references')
        pdf_record = existing_record or PDFRecord(id=cls.new_id(doi))
        pdf_record.authors = (authors and json.dumps(authors)) or '[]'
        pdf_record.published_date = parsed_pdf_json.get('published_date')
        pdf_record.genre = parsed_pdf_json.get('genre')
        pdf_record.abstract = parsed_pdf_json.get('abstract')
        pdf_record.citations = (references and json.dumps(references)) or '[]'
        pdf_record.doi = doi
        pdf_record.work_id = -1
        pdf_record.updated = datetime.datetime.utcnow().isoformat()

        return pdf_record
