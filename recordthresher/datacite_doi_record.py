import datetime
import hashlib
import json
import uuid

import shortuuid

from app import db, logger
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

        datacite_row = DataCiteRaw.query.get(doi)
        datacite_work = datacite_row.datacite_api_raw if datacite_row else None
        if not datacite_work:
            return None

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'datacite_record:{doi}'.encode('utf-8')).digest()[0:16])
        )

        record = DataCiteDoiRecord.query.get(record_id)
        is_new = False

        if not record:
            record = DataCiteDoiRecord(id=record_id)
            is_new = True

        # doi
        record.doi = clean_doi(datacite_work['id'])

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
        for date in datacite_work['attributes'].get('dates', []):
            if date['dateType'] == 'Issued':
                if date['date'] and len(date['date']) == 4:
                    record.published_date = f'{date["date"]}-01-01'
                record.published_date = date['date']

        # genre
        genre = datacite_work['attributes'].get('types', {}).get('bibtex', None)
        genre = genre.lower().strip() if genre else None
        record.genre = genre

        # publisher
        record.publisher = datacite_work['attributes'].get('publisher', None)

        # webpage url
        record.record_webpage_url = datacite_work['attributes'].get('url', None)

        # license
        for rights in datacite_work['attributes'].get('rightsList', []):
            if rights.get('rightsIdentifier', None):
                record.open_license = rights.get('rightsIdentifier', None)

        # funders
        record.funders = []
        for funder in datacite_work['attributes'].get('fundingReferences', []):
            record_funder = {
                'name': funder.get('funderName', None),
                'award': funder.get('awardNumber', None),
                'doi': funder.get('funderIdentifier', None)
            }
            record.funders.append(record_funder)

        record.authors = json.dumps(record.authors)
        record.funders = json.dumps(record.funders)

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        if is_new:
            logger.info(f'created record {record.id} from doi {doi}')
        else:
            logger.info(f'updated record {record.id} from doi {doi}')
        return record
