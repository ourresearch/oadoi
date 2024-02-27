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

        datacite_raw = DataCiteRaw.query.get(doi)
        if not datacite_raw:
            return None

        record = DataCiteRecord.query.get(id=doi)

        if not record:
            record = DataCiteRecord(id=doi)

        # doi
        record.doi = datacite_raw['id']

        # title
        record.title = datacite_raw['attributes']['titles'][0]['title'] if datacite_raw['attributes']['titles'] else None
        record.normalized_title = normalize_title(record.title)

        # authors
        record.authors = []
        for author in datacite_raw['attributes'].get('creators', []):
            record.authors.append(author['name'])

        # abstract
        descriptions = datacite_raw['attributes'].get('descriptions', [])
        abstract = next((d['description'] for d in descriptions if d['descriptionType'] == 'Abstract'), None)
        record.abstract = abstract

        # published date
        record.published_date = datacite_raw['attributes'].get('published', None)

        # genre
        record.genre = datacite_raw['attributes'].get('types', {}).get('resourceTypeGeneral', None)

        # publisher
        record.publisher = datacite_raw['attributes'].get('publisher', None)

        # webpage url
        record.record_webpage_url = datacite_raw['attributes'].get('url', None)

        # license
        record.open_license = datacite_raw['attributes'].get('rightsList', [{}])[0].get('rightsIdentifier', None)
