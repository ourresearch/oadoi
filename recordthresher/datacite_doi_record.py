import datetime
import hashlib
import uuid

import shortuuid

from app import db
from recordthresher.record import Record
from recordthresher.datacite import DataCiteRaw
from util import clean_doi, normalize_title


class DataCiteDoiRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'datacite_doi'}

    @staticmethod
    def from_doi(doi):
        if not doi:
            return None

        datacite_work = DataCiteRaw.query.get(doi)
        if not datacite_work:
            return None

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'datacite_record:{doi}'.encode('utf-8')).digest()[0:16])
        )

        record = DataCiteDoiRecord.query.get(id=record_id)

        if not record:
            record = DataCiteDoiRecord(id=record_id)

        # doi
        record.doi = clean_doi(datacite_work['doi'])

        # title
        record.title = datacite_work['attributes']['titles'][0]['title'] if datacite_work['attributes']['titles'] else None
        record.normalized_title = normalize_title(record.title)

        # authors
        record.authors = []
        for datacite_author in datacite_work['attributes'].get('creators', []):
            record_author = {
                'name': datacite_author.get('name', None),
                'family': datacite_author.get('familyName', None),
                'given': datacite_author.get('givenName', None),
                'affiliation': [{"name": aff} for aff in datacite_author.get('affiliation', None)]
            }
            for name_identifier in datacite_author.get('nameIdentifiers', []):
                if name_identifier['nameIdentifierScheme'] == 'ORCID':
                    record_author['orcid'] = name_identifier['nameIdentifier']
            record.authors.append(record_author)

        # abstract
        descriptions = datacite_work['attributes'].get('descriptions', [])
        abstract = next((d['description'] for d in descriptions if d['descriptionType'] == 'Abstract'), None)
        record.abstract = abstract

        # published date
        record.published_date = datacite_work['attributes'].get('published', None)

        # genre
        genre = datacite_work['attributes'].get('types', {}).get('resourceTypeGeneral', None)
        genre = genre.lower().strip() if genre else None
        record.genre = genre

        # publisher
        record.publisher = datacite_work['attributes'].get('publisher', None)

        # webpage url
        record.record_webpage_url = datacite_work['attributes'].get('url', None)

        # license
        record.open_license = datacite_work['attributes'].get('rightsList', [{}])[0].get('rightsIdentifier', None)

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()
