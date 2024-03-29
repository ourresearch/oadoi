import logging
from datetime import datetime

from sqlalchemy import text

from util import get_openalex_json, make_default_logger, normalize_doi
from app import oa_db_engine

DEFAULT_FILTER = 'has_raw_affiliation_string:false,type:article,has_doi:true'

TOTAL_ENQUEUED_WORKS = 0
TOTAL_SEEN = 0

STARTED = datetime.now()


ENQUEUE_CHUNK_SIZE = 200

LOGGER: logging.Logger = make_default_logger('passive_enqueue_affs')


def works_no_affs_iterator(filter_=DEFAULT_FILTER):
    has_more = True
    params = {
        'filter': filter_,
        'cursor': '*',
        'per-page': '200',
        'select': 'id,doi',
        'mailto': 'dev@ourresearch.org'
    }
    while has_more:
        j = get_openalex_json('https://api.openalex.org/works', params=params)
        results = j['results']
        for work in results:
            if work:
                yield work
        next_cursor = j['meta'].get('next_cursor')
        has_more = bool(next_cursor)
        params['cursor'] = next_cursor


def enqueue_works_missing_affs():
    global TOTAL_ENQUEUED_WORKS
    global TOTAL_SEEN
    dois = []
    no_affs_iterator = works_no_affs_iterator()
    with oa_db_engine.connect() as db_conn:
        for work in no_affs_iterator:
            dois.append(work['doi'].split('.org/')[-1])
            if len(dois) >= ENQUEUE_CHUNK_SIZE:
                stmnt = text("""SELECT work_id FROM ins.recordthresher_record WHERE work_id != -1 and record_type = 'crossref_doi' AND doi in (SELECT doi
                                                                 FROM ins.recordthresher_record
                                                                 WHERE record_type = 'crossref_parseland' AND EXISTS (SELECT 1
                                                                               FROM jsonb_array_elements(authors::jsonb) AS author
                                                                               WHERE jsonb_array_length(author -> 'affiliations') > 0) AND doi IN :dois)""")
                r = db_conn.execute(stmnt, dois=tuple(dois))
                work_ids = [row[0] for row in r.fetchall()]
                work_ids_tmpl = ','.join(['(%s)'] * len(work_ids))
                if work_ids:
                    stmnt = db_conn.connection.cursor().mogrify(f'INSERT INTO queue.run_once_work_add_most_things(work_id) VALUES {work_ids_tmpl} ON CONFLICT(work_id) DO NOTHING;', work_ids)
                    db_conn.execute(stmnt.decode())
                TOTAL_ENQUEUED_WORKS += len(work_ids)
                TOTAL_SEEN += ENQUEUE_CHUNK_SIZE
                hrs_running = round((datetime.now() - STARTED).total_seconds() / (60 * 60), 3)
                seen_rate = round(TOTAL_SEEN/ hrs_running, 2) if hrs_running else 0
                LOGGER.info(f'[*] Enqueued {len(work_ids)} works | Total enqueued: {TOTAL_ENQUEUED_WORKS} | Total seen: {TOTAL_SEEN} | Seen rate: {seen_rate}/hr | Hrs running: {hrs_running} hrs')
                dois = []


if __name__ == '__main__':
    enqueue_works_missing_affs()
