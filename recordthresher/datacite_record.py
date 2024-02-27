import hashlib
import uuid

import shortuuid

from recordthresher.record import Record
from recordthresher.datacite import DataCiteRaw
from util import clean_doi, normalize_title


class DataCiteRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'datacite_record'}

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

        record = DataCiteRecord.query.get(id=record_id)

        if not record:
            record = DataCiteRecord(id=record_id)

        # doi
        record.doi = datacite_work['id']

        # title
        record.title = datacite_work['attributes']['titles'][0]['title'] if datacite_work['attributes']['titles'] else None
        record.normalized_title = normalize_title(record.title)

        # authors
        record.authors = []
        for author in datacite_work['attributes'].get('creators', []):
            record.authors.append(author['name'])

        # abstract
        descriptions = datacite_work['attributes'].get('descriptions', [])
        abstract = next((d['description'] for d in descriptions if d['descriptionType'] == 'Abstract'), None)
        record.abstract = abstract

        # published date
        record.published_date = datacite_work['attributes'].get('published', None)

        # genre
        record.genre = datacite_work['attributes'].get('types', {}).get('resourceTypeGeneral', None)

        # publisher
        record.publisher = datacite_work['attributes'].get('publisher', None)

        # webpage url
        record.record_webpage_url = datacite_work['attributes'].get('url', None)

        # license
        record.open_license = datacite_work['attributes'].get('rightsList', [{}])[0].get('rightsIdentifier', None)
