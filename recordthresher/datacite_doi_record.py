import datetime
import hashlib
import json
import uuid

import shortuuid

from app import db, logger
from recordthresher.record import Record
from recordthresher.datacite import DataCiteRaw, DataCiteVersion, DataCiteClient
from util import clean_doi, normalize_title

"""
Ingest a DataCite DOI record into the database with this command:
heroku local:run python -- queue_datacite_doi.py --doi 10.5281/zenodo.123456
"""

ALLOWED_DATACITE_TYPES = [
    "book",
    "book-chapter",
    "collection",
    "conference-paper",
    "conference-proceeding",
    "dataset",
    "dissertation",
    "journal-article",
    "model",
    "preprint",
    "report",
    "software",
    "text",
]


class DataCiteDoiRecord(Record):
    __tablename__ = None

    __mapper_args__ = {'polymorphic_identity': 'datacite_doi'}

    @staticmethod
    def from_doi(cls, doi):
        if not doi:
            return None

        datacite_work = cls.get_datacite_work(doi)

        datacite_type = datacite_work['attributes'].get('types', {}).get('resourceTypeGeneral', None)
        is_active = datacite_work['attributes'].get('isActive', None)

        # skip it if
        if (
            not datacite_work
            or not datacite_type
            or datacite_type.lower().strip() not in ALLOWED_DATACITE_TYPES
            or not is_active
        ):
            logger.info(f"skipping doi {doi} with type {datacite_type} and is_active {is_active}")
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
        record.set_oa(datacite_work)
        record.set_license(datacite_work)
        record.set_citations(datacite_work)
        record.set_funders(datacite_work)
        record.set_repository_id(datacite_work)
        record.set_arxiv_id(datacite_work)
        record.save_related_versions(datacite_work)

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
        print(f"title: {self.title}")

    def set_authors(self, datacite_work):
        self.authors = []
        for datacite_author in datacite_work['attributes'].get('creators', []):
            # author name
            record_author = {
                'name': datacite_author.get('name', None),
                'raw': datacite_author.get('name', None),
                'family': datacite_author.get('familyName', None),
                'given': datacite_author.get('givenName', None)
            }

            # orcid
            record_author['orcid'] = None
            for name_identifier in datacite_author.get('nameIdentifiers', []):
                if name_identifier['nameIdentifierScheme'] == 'ORCID':
                    record_author['orcid'] = name_identifier['nameIdentifier']

            # affiliations
            record_author['affiliation'] = []
            for affiliation in datacite_author.get('affiliation', []):
                formatted_affiliation = {}
                formatted_affiliation['name'] = affiliation.get('name', None) or affiliation.get('affiliation', None)
                ror = affiliation.get('affiliationIdentifier', None) if affiliation.get('affiliationIdentifierScheme') == 'ROR' else None
                if ror:
                    formatted_affiliation['ror'] = ror
                record_author['affiliation'].append(formatted_affiliation)

            self.authors.append(record_author)
        self.authors = json.dumps(self.authors)
        print(f"authors: {self.authors}")

    def set_abstract(self, datacite_work):
        descriptions = datacite_work['attributes'].get('descriptions', [])
        abstract = next((d['description'] for d in descriptions if d['descriptionType'] == 'Abstract'), None)
        self.abstract = abstract
        print(f"abstract: {self.abstract}")

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

    def set_oa(self, datacite_work):
        oa = None
        for rights in datacite_work['attributes'].get('rightsList', []):
            if rights.get('rights', None):
                oa = 'open' in rights.get('rights', '').lower()
        self.is_oa = oa
        print(f"is_oa: {self.is_oa}")

    def set_license(self, datacite_work):
        open_license = None
        for rights in datacite_work['attributes'].get('rightsList', []):
            if rights.get('rightsIdentifier', None):
                open_license = rights.get('rightsIdentifier', None)

        if not open_license:
            for rights in datacite_work['attributes'].get('rightsList', []):
                if rights.get('rights', None):
                    open_license = rights.get('rights', None)

        self.open_license = open_license
        print(f"open_license: {self.open_license}")

    def set_citations(self, datacite_work):
        citations = []
        for related_identifier in datacite_work['attributes'].get('relatedIdentifiers', []):
            if related_identifier['relationType'] == 'References':
                citations.append(related_identifier['relatedIdentifier'])
        self.citations = json.dumps(citations)
        print(f"citations: {self.citations}")

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

    def set_repository_id(self, datacite_work):
        client_id = datacite_work['relationships'].get('client', {}).get('data', {}).get('id', None)
        repository = DataCiteClient.query.get(client_id)
        self.repository_id = repository.endpoint_id if repository else None
        print(f"repository_id: {self.repository_id}")

    def set_arxiv_id(self, datacite_work):
        raw_id = next((id['identifier'] for id in datacite_work['attributes'].get('identifiers', []) if id['identifierType'] == 'arXiv'), None)
        self.arxiv_id = f"arXiv:{raw_id}" if raw_id and not raw_id.startswith("arXiv:") else None
        print(f"arxiv_id: {self.arxiv_id}")

    def save_related_versions(self, datacite_work):
        related_dois = []
        version_keys = ['IsVersionOf', 'IsNewVersionOf', 'HasVersion']
        for related_identifier in datacite_work['attributes'].get('relatedIdentifiers', []):
            if related_identifier['relatedIdentifierType'] == 'DOI' and related_identifier['relationType'] in version_keys:
                related_dois.append(related_identifier['relatedIdentifier'])
        for doi in related_dois:
            related_doi = DataCiteVersion(datacite_doi=self.doi, related_doi=doi)
            db.session.merge(related_doi)
        print(f"related_dois: {related_dois}")
