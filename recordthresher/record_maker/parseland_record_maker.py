import datetime
import hashlib
import json
import uuid

import shortuuid

from app import logger
from recordthresher.crossref_parseland_record import CrossrefParselandRecord
from recordthresher.util import parser_response


def parseland_api_url(pub):
    return f'https://parseland.herokuapp.com/parse-publisher?doi={pub.id}'


def affiliations_count(pl_response):
    count = 0
    for author in pl_response.get('authors'):
        count += len((author.get('affiliations', []) or []))
    return count


class ParselandRecordMaker:
    @classmethod
    def make_record(cls, pub, update_existing=True):
        if not (pub and hasattr(pub, 'id') and pub.id):
            return None

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(
                f'parseland:{pub.id}'.encode('utf-8')).digest()[0:16])
        )

        pl_record = CrossrefParselandRecord.query.get(record_id)

        if pl_record and not update_existing:
            logger.info(
                f"not updating existing parseland record {pl_record.id}")
            return None

        pl_response = parser_response(parseland_api_url(pub))

        if not pl_response:
            logger.info(
                f"didn't get a parseland response for {pub.id}, not making record")
            return None
        elif pl_record and affiliations_count(pl_response) == 0:
            logger.info(f'parseland response for {pub.id} returned 0 affiliations, not updating existing parseland record {pl_record.id}')
            return None

        pl_authors = pl_response.get('authors')

        pl_record = pl_record or CrossrefParselandRecord(id=record_id)
        pl_record.authors = (pl_authors and json.dumps(pl_authors)) or '[]'
        pl_record.published_date = pl_response.get('published_date')
        pl_record.genre = pl_response.get('genre')
        pl_record.abstract = pl_response.get('abstract')
        pl_record.doi = pub.id
        pl_record.work_id = -1
        pl_record.updated = datetime.datetime.utcnow().isoformat()

        return pl_record
