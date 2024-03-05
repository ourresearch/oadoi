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
    def from_doi(cls, doi):
        if not doi:
            return None

        datacite_work = cls.get_datacite_work(doi)

        if not datacite_work:
            return None

        record = cls.get_or_create_record(doi)

        record.doi = clean_doi(datacite_work['id'])
        record.set_title(datacite_work)
        record.set_authors(datacite_work)
        record.set_abstract(datacite_work)
        record.set_published_date(datacite_work)
        record.set_genre(datacite_work)
        record.publisher = datacite_work['attributes'].get('publisher', None)
        record.record_webpage_url = datacite_work['attributes'].get('url', None)
        record.set_license(datacite_work)
        record.set_funders(datacite_work)
        record.set_repo_id(datacite_work)

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        return record

    @classmethod
    def get_datacite_work(cls, doi):
        datacite_row = DataCiteRaw.query.get(doi)
        return datacite_row.datacite_api_raw if datacite_row else None

    @classmethod
    def get_or_create_record(cls, doi):
        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'datacite_record:{doi}'.encode('utf-8')).digest()[0:16])
        )
        record = cls.query.get(record_id)
        if not record:
            record = cls(id=record_id)
            logger.info(f'creating record {record.id} from datacite doi {doi}')
        else:
            logger.info(f'updating record {record.id} from datacite doi {doi}')
        return record

    def set_title(self, datacite_work):
        self.title = datacite_work['attributes']['titles'][0]['title'] if datacite_work['attributes']['titles'] else None
        self.normalized_title = normalize_title(self.title)

    def set_authors(self, datacite_work):
        self.authors = []
        for datacite_author in datacite_work['attributes'].get('creators', []):
            record_author = {
                'name': datacite_author.get('name', None),
                'family': datacite_author.get('familyName', None),
                'given': datacite_author.get('givenName', None),
                'affiliation': [aff for aff in datacite_author.get('affiliation', None)]
            }
            for name_identifier in datacite_author.get('nameIdentifiers', []):
                if name_identifier['nameIdentifierScheme'] == 'ORCID':
                    record_author['orcid'] = name_identifier['nameIdentifier']
            self.authors.append(record_author)
        self.authors = json.dumps(self.authors)
        print(f"authors: {self.authors}")

    def set_abstract(self, datacite_work):
        descriptions = datacite_work['attributes'].get('descriptions', [])
        abstract = next((d['description'] for d in descriptions if d['descriptionType'] == 'Abstract'), None)
        self.abstract = abstract

    def set_published_date(self, datacite_work):
        published_date = None
        for date in datacite_work['attributes'].get('dates', []):
            if date['dateType'] == 'Issued':
                if date['date'] and len(date['date'].strip()) == 4:
                    published_date = f'{date["date"].strip()}-01-01'
                else:
                    published_date = date['date'].strip()

        if not published_date:
            # fall back to publicationYear
            published_year = datacite_work['attributes'].get('publicationYear', None)
            published_date = f'{published_year}-01-01' if published_year else None
        self.published_date = published_date
        print("published_date: ", self.published_date)

    def set_genre(self, datacite_work):
        genre = datacite_work['attributes'].get('types', {}).get('resourceTypeGeneral', None)
        genre = genre.lower().strip() if genre else None
        self.genre = genre
        print("genre: ", self.genre)

    def set_license(self, datacite_work):
        for rights in datacite_work['attributes'].get('rightsList', []):
            if rights.get('rightsIdentifier', None):
                self.open_license = rights.get('rightsIdentifier', None)

    def set_funders(self, datacite_work):
        self.funders = []
        for funder in datacite_work['attributes'].get('fundingReferences', []):
            record_funder = {
                'name': funder.get('funderName', None),
                'award': funder.get('awardNumber', None),
                'doi': funder.get('funderIdentifier', None)
            }
            self.funders.append(record_funder)
        self.funders = json.dumps(self.funders)
        print(f"funders: {self.funders}")

    def set_repo_id(self, datacite_work):
        self.repo_id = datacite_work['relationships'].get('client', {}).get('data', {}).get('id', None)
        print(f"repo_id: {self.repo_id}")