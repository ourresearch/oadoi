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
    def make_record(cls, pub, update_existing=True):
        if not (pub and hasattr(pub, 'id') and pub.id):
            return None

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(
                f'parsed_pdf:{pub.id}'.encode('utf-8')).digest()[0:16])
        )

        pdf_record = PDFRecord.query.get(record_id)

        if pdf_record and not update_existing:
            logger.info(
                f"not updating existing pdf record {pdf_record.id}")
            return None

        r_json = pdf_parser_response(pdf_parse_api_url(pub))
        msg = r_json.get('message', {}) or {}

        has_data = any([bool(msg.get(key)) for key in r_json.keys()])

        if not r_json or not has_data:
            logger.info(
                f"didn't get a pdf parse response for {pub.id}, not making record")
            return None

        authors = r_json.get('authors')
        references = r_json.get('references')
        pdf_record = pdf_record or PDFRecord(id=record_id)
        pdf_record.authors = (authors and json.dumps(authors)) or '[]'
        pdf_record.published_date = r_json.get('published_date')
        pdf_record.genre = r_json.get('genre')
        pdf_record.abstract = r_json.get('abstract')
        pdf_record.citations = (references and json.dumps(references)) or '[]'
        pdf_record.doi = pub.id
        pdf_record.work_id = -1
        pdf_record.updated = datetime.datetime.utcnow().isoformat()

        return pdf_record
