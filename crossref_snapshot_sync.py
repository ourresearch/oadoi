import datetime
import os

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import logger
from pub import Pub
from pub import build_new_pub
from util import normalize_doi
from util import safe_commit

import endpoint  # magic

"""
Run this script after staging a crossref snapshot with the `crossref_snapshot_staging.py` script.
This will update the `pub` table with the latest crossref data, similar to put_crossref_in_db.py.
"""


class MonthlySync(db.Model):
    __tablename__ = 'temp_crossref_monthly_sync'

    id = db.Column(db.Integer, primary_key=True)
    response_jsonb = db.Column(JSONB)


def iso_to_datetime(iso_str):
    return datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")


def add_pubs_or_update_crossref(pubs):
    if not pubs:
        return []

    pubs_by_id = dict((p.id, p) for p in pubs)

    existing_pub_ids = set([
        id_tuple[0] for id_tuple in db.session.query(Pub.id).filter(Pub.id.in_(list(pubs_by_id.keys()))).all()
    ])

    pubs_to_add = [p for p in pubs if p.id not in existing_pub_ids]
    pubs_to_update = [p for p in pubs if p.id in existing_pub_ids]

    if pubs_to_add:
        logger.info("adding {} pubs".format(len(pubs_to_add)))
        db.session.add_all(pubs_to_add)

    if pubs_to_update:
        row_dicts = [{'id': p.id, 'crossref_api_raw_new': p.crossref_api_raw_new} for p in pubs_to_update]
        logger.info("updating {} pubs".format(len(pubs_to_update)))
        db.session.bulk_update_mappings(Pub, row_dicts)

    db.session.execute(
        text(
            '''
            insert into recordthresher.doi_record_queue (doi, updated) (
                select id, (crossref_api_raw_new->'indexed'->>'date-time')::timestamp without time zone from pub
                where id = any (:dois)
            ) ON CONFLICT (doi) DO UPDATE SET updated = excluded.updated
            '''
        ).bindparams(dois=list(set(pubs_by_id.keys())))
    )

    safe_commit(db)
    return pubs_to_add


def needs_update(sync_record, pub):
    sr_dt = sync_record.response_jsonb['indexed']['date-time']
    pub_dt = pub.crossref_api_raw_new['indexed']['date-time']
    difference = abs(iso_to_datetime(pub_dt) - iso_to_datetime(sr_dt))
    if difference <= datetime.timedelta(minutes=20):
        # do not update when index timestamps are less than 20 minutes apart
        return False
    elif pub_dt > sr_dt:
        # do not update if record in database is newer than record in crossref monthly snapshot
        return False
    else:
        logger.info("needs update: {} {}".format(pub.id, difference))
        return True


def needs_creation(pub):
    if not pub:
        return True


def get_dois_and_data_from_crossref(chunk_size=100):
    num_pubs_added_so_far = 0
    insert_pub_fn = add_pubs_or_update_crossref

    offset = int(os.getenv('MONTHLY_SYNC_OFFSET', 0))
    while True:
        pubs_this_chunk = []
        logger.info(f"getting dois from crossref, offset {offset}")
        sync_records = MonthlySync.query.order_by(MonthlySync.id).offset(offset).limit(chunk_size).all()

        if not sync_records:
            break

        logger.info(f"got {len(sync_records)} sync records")
        dois = [normalize_doi(sync_record.response_jsonb['DOI']) for sync_record in sync_records]

        logger.info(f"getting {len(dois)} pubs from db")
        pubs = {pub.id: pub for pub in Pub.query.filter(Pub.id.in_(dois)).all()}

        for sync_record in sync_records:
            doi = normalize_doi(sync_record.response_jsonb['DOI'])
            pub = pubs.get(doi, None)
            if needs_update(sync_record, pub) or needs_creation(pub):
                my_pub = build_new_pub(doi, sync_record.response_jsonb)
                # hack so it gets updated soon
                my_pub.updated = datetime.datetime(1042, 1, 1)
                pubs_this_chunk.append(my_pub)

        added_pubs = insert_pub_fn(pubs_this_chunk)
        logger.info("added {} pubs, loop done".format(len(added_pubs), ))
        num_pubs_added_so_far += len(added_pubs)

        # Update the offset for the next batch
        offset += chunk_size
        logger.info("Processed up to offset {}".format(offset))

    # make sure to get the last ones
    if pubs_this_chunk:
        logger.info("saving last ones")
        added_pubs = insert_pub_fn(pubs_this_chunk)
        num_pubs_added_so_far += len(added_pubs)

    logger.info("Added >>{}<< new crossref dois on {}".format(
        num_pubs_added_so_far, datetime.datetime.now().isoformat()[0:10]))


if __name__ == "__main__":
    get_dois_and_data_from_crossref()
