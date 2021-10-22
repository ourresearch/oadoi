import datetime
import hashlib
import json
import uuid
from copy import deepcopy
from sys import stdin

import shortuuid

from app import db
from recordthresher.pmh_record_record import PmhRecordRecord
from recordthresher.util import normalize_author, normalize_citation
from util import clean_doi


def _run():
    commit_chunk = 100
    this_chunk_size = 0

    for line in stdin:
        json_record = json.loads(line)

        title = json_record.get('title')
        record_type = json_record.get('type')
        dblp_key = json_record.get('dblp_key')

        if not (dblp_key and title and record_type in ['article', 'phdthesis']):
            continue

        record_id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(f'dblp_record:{dblp_key}'.encode('utf-8')).digest()[0:16])
        )

        record = PmhRecordRecord.query.get(record_id)

        if not record:
            record = PmhRecordRecord(id=record_id)

        record.pmh_id = dblp_key
        record.repository_id = 'dblp'

        record.title = title
        record.genre = record_type

        authors = []

        if record_type == 'article':
            for author in json_record.get('authors', []):
                authors.append(normalize_author(author))

        if record_type == 'phdthesis':
            if author_list := json_record.get('authors'):
                author = deepcopy(author_list[0])
                if schools_list := json_record.get('schools'):
                    author['affiliation'] = [{'name': schools_list[0]}]

                authors.append(normalize_author(author))

        record.set_jsonb('authors', authors)

        cites = []

        for cite in json_record.get('cites', []):
            if cite_key := cite.get('key'):
                if '/' in cite_key:
                    cites.append(normalize_citation({'unstructured': f'https://dblp.org/rec/{cite_key}.html'}))

        record.set_jsonb('citations', cites)

        for url in json_record.get('urls', []):
            if 'doi.org/10.' in url:
                if url_doi := clean_doi(url, return_none_if_error=True):
                    record.doi = url_doi
                    break

        record.record_webpage_url = f'https://dblp.org/rec/{dblp_key}.html'
        record.record_structured_url = f'https://dblp.org/rec/{dblp_key}.xml'

        record.is_oa = False

        if db.session.is_modified(record):
            record.updated = datetime.datetime.utcnow().isoformat()

        db.session.merge(record)
        this_chunk_size += 1

        if this_chunk_size >= commit_chunk:
            print(f'saving {this_chunk_size} records')
            db.session.commit()
            this_chunk_size = 0

    print(f'saving {this_chunk_size} records')
    db.session.commit()


if __name__ == '__main__':
    _run()
