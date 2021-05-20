import argparse
from datetime import timedelta
from time import time

import requests
from sqlalchemy import or_

from app import db, logger
from journal import Journal
from util import elapsed, safe_commit


def run(retry_apis):
    start = time()

    journal_ids = db.session.query(Journal.issn_l).filter(
        or_(
            missing_field_filter(Journal.api_raw_crossref, retry_apis),
            missing_field_filter(Journal.api_raw_issn, retry_apis),
        )
    ).all()

    logger.info('trying to update {} journals'.format(len(journal_ids)))

    chunk_size = 50
    for i in range(0, len(journal_ids), chunk_size):
        id_chunk = journal_ids[i:i+chunk_size]
        journals = Journal.query.filter(Journal.issn_l.in_(id_chunk)).all()

        for journal in journals:
            # try all issns, issn-l first
            issns = set(journal.issns)
            issns.discard(journal.issn_l)
            issns = [journal.issn_l] + list(issns)

            if journal.api_raw_crossref is None or (retry_apis and journal.api_raw_crossref == {}):
                logger.info('getting crossref api response for {}'.format(journal.issn_l))
                journal.api_raw_crossref = get_first_response(call_crossref_api, issns) or {}

            if journal.api_raw_issn is None or (retry_apis and journal.api_raw_issn == {}):
                logger.info('getting issn api response for {}'.format(journal.issn_l))
                journal.api_raw_issn = get_first_response(call_issn_api, issns) or {}

            db.session.merge(journal)

        safe_commit(db)

    db.session.remove()

    logger.info('finished update in {}'.format(timedelta(seconds=elapsed(start))))


def missing_field_filter(api_response_field, retry_apis):
    #  don't look up things we already tried and got no response for unless retry_apis is set
    if retry_apis:
        return or_(api_response_field.is_(None), api_response_field == {})
    else:
        return api_response_field.is_(None)


def call_json_api(url_template, query_text):
    response_data = None

    url = url_template.format(query_text)
    logger.info('getting {}'.format(url))

    r = requests.get(url)
    if r.status_code == 200:
        try:
            response_data = r.json()
        except ValueError:
            pass

    return response_data


def call_issn_api(issn):
    return call_json_api('https://portal.issn.org/resource/ISSN/{}?format=json', issn)


def call_crossref_api(issn):
    return call_json_api('https://api.crossref.org/journals/{}', issn)


def get_first_response(api_fn, issns):
    for issn in issns:
        result = api_fn(issn)
        if result:
            logger.info('got a response for {}({})'.format(api_fn.__name__, issn))
            return result

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get Crossref and issn.org metadata for journals.")
    parser.add_argument('--retry-apis', default=False, action='store_true', help="look up journals again if we already tried and got no response")

    parsed = parser.parse_args()
    run(parsed.retry_apis)
