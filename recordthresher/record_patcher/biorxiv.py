import requests

from recordthresher.util import normalize_author
from .patcher import CrossrefDoiPatcher

import datetime


class BiorxivPatcher(CrossrefDoiPatcher):
    @classmethod
    def _should_patch_record(cls, record, pub):
        if pub.doi.startswith('10.1101/') and pub.genre == 'posted-content':
            xref_institution = pub.crossref_api_raw_new.get('institution', {})
            if isinstance(xref_institution, list) and xref_institution:
                xref_institution = xref_institution[0]

            if xref_institution:
                xref_institution_name = xref_institution.get('name', None)
            else:
                xref_institution_name = None

            return xref_institution_name == 'bioRxiv'
        else:
            return False

    @classmethod
    def _patch_record(cls, record, pub):
        print(datetime.datetime.utcnow())
        authors = []
        parseland_parse = requests.get(f'http://localhost:5000/parse-publisher?doi={pub.id}')
        if parseland_parse.ok:
            parseland_json = parseland_parse.json()
            for author in parseland_json['message']:
                record_author = {'raw': author['name'], 'affiliation': [{'name': x} for x in author['affiliations']]}
                authors.append(normalize_author(record_author))
        print(datetime.datetime.utcnow())

        record.set_authors(authors)
