from record_maker import RecordMaker
from recordthresher.datacite_record import DataCiteRecord

from util import normalize, normalize_title, NoDoiException


class DataCiteRecordMaker(RecordMaker):
    @classmethod
    def _make_record_impl(cls, datacite_raw):
        record = DataCiteRecord.query.get(datacite_raw['id']) or DataCiteRecord(id=datacite_raw['id'])

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
        record.genre = datacite_raw['attributes'].get('resourceType', {}).get('resourceTypeGeneral', None)

        # publisher
        record.publisher = datacite_raw['attributes'].get('publisher', None)

        # citations
        references = datacite_raw['attributes'].get('references', [])

        # webpage url
        record.record_webpage_url = datacite_raw['attributes'].get('url', None)