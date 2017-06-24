import os
import sickle
import boto
import datetime
import requests
from time import sleep
from time import time
import zlib
import re
import sys
import json
import argparse
import random
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import logger
from util import safe_commit
from util import elapsed
from util import is_doi_url
from util import clean_doi
from publication import Base
from publication import call_targets_in_parallel
from oa_base import get_urls_from_our_base_doc
from oa_local import find_normalized_license
from webpage import WebpageInUnknownRepo

# set up elasticsearch
INDEX_NAME = "base"
TYPE_NAME = "record"


class MissingTagException(Exception):
    pass




def find_fulltext_for_base_hits(base_hits):
    records_to_save = []
    base_objects = []

    for base_hit in base_hits:
        my_base = Base()
        my_base.set_doc(base_hit.doc)
        base_objects.append(my_base)

    scrape_start = time()

    targets = [base_obj.find_fulltext for base_obj in base_objects]
    call_targets_in_parallel(targets)
    logger.info(u"scraping {} webpages took {} seconds".format(len(base_objects), elapsed(scrape_start, 2)))


def oai_tag_match(tagname, record, return_list=False):
    if not tagname in record.metadata:
        return None
    matches = record.metadata[tagname]
    if return_list:
        return matches  # will be empty list if we found naught
    else:
        try:
            return matches[0]
        except IndexError:  # no matches.
            return None


def tag_match(tagname, str, return_list=False):
    regex_str = "<{}>(.+?)</{}>".format(tagname, tagname)
    matches = re.findall(regex_str, str)

    if return_list:
        return matches  # will be empty list if we found naught
    else:
        try:
            return matches[0]
        except IndexError:  # no matches.
            return None


def is_complete(record):
    required_keys = [
        "id",
        "title",
        "urls"
    ]

    for k in required_keys:
        if not record[k]:  # empty list is falsey
            # logger.info(u"Record is missing required key '{}'!".format(k))
            return False

    if record["oa"] == 0:
        logger.info(u"record {} is closed access. skipping.".format(record["id"]))
        return False

    return True



def safe_get_next_record(records):
    try:
        next_record = records.next()
    except requests.exceptions.HTTPError:
        logger.info("HTTPError exception!  skipping")
        return safe_get_next_record(records)
    except (KeyboardInterrupt, SystemExit):
        # done
        return None
    except Exception:
        raise
        logger.info("misc exception!  skipping")
        return safe_get_next_record(records)
    return next_record




def oaipmh_to_db(first=None, last=None, today=None, collection=None, chunk_size=10, id=None):

    if id:
        my_base = Base.query.get(id)
        my_base.find_fulltext()
        db.session.merge(my_base)
        safe_commit(db)
        return

    proxy_url = os.getenv("STATIC_IP_PROXY")
    proxies = {"https": proxy_url, "http": proxy_url}
    base_sickle = sickle.Sickle("http://oai.base-search.net/oai", proxies=proxies)

    if today:
        last = datetime.date.today().isoformat()
        first = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    args = {'metadataPrefix': 'base_dc', 'from': first, }
    if last:
        args["until"] = last

    if collection:
        args["set"] = u"collection:{}".format(collection)

    oai_records = base_sickle.ListRecords(ignore_deleted=True, **args)

    base_objects = []
    oai_record = safe_get_next_record(oai_records)
    while oai_record:
        record = {}
        record["id"] = oai_record.header.identifier
        record["base_timestamp"] = oai_record.header.datestamp
        record["added_timestamp"] = datetime.datetime.utcnow().isoformat()

        record["title"] = oai_tag_match("title", oai_record)
        record["license"] = oai_tag_match("rights", oai_record)
        try:
            record["oa"] = int(oai_tag_match("oa", oai_record))
        except TypeError:
            record["oa"] = 0

        record["urls"] = oai_tag_match("identifier", oai_record, return_list=True)
        record["authors"] = oai_tag_match("creator", oai_record, return_list=True)
        record["relations"] = oai_tag_match("relation", oai_record, return_list=True)
        record["sources"] = oai_tag_match("collname", oai_record, return_list=True)

        if is_complete(record):
            record_body = {"_id": record["id"], "_source": record}
            record_doi = None
            for url in record["urls"]:
                if is_doi_url(url):
                    record_doi = clean_doi(url)
            my_base = Base(id=record["id"], body=record_body, doi=record_doi)
            logger.info("my_base:", my_base)
            db.session.merge(my_base)
            base_objects.append(my_base)
            logger.info(":")
        else:
            logger.info(".")

        if len(base_objects) >= chunk_size:
            find_fulltext_for_base_hits(base_objects)
            logger.info("last record saved:", base_objects[-1])
            logger.info(u"committing")
            safe_commit(db)
            base_objects = []

        oai_record = safe_get_next_record(oai_records)

    # make sure to get the last ones
    logger.info("saving last ones")
    find_fulltext_for_base_hits(base_objects)
    safe_commit(db)
    logger.info("done everything")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = oaipmh_to_db
    parser.add_argument('--first', type=str, help="first date to pull stuff from oai-pmh (example: --start_date 2016-11-10")
    parser.add_argument('--last', type=str, help="last date to pull stuff from oai-pmh (example: --end_date 2016-11-10")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in base records from last 2 days")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=10, help="how many rows before a db commit")
    parser.add_argument('--collection', nargs="?", type=str, default=None, help="specific collection? ie ftimperialcol")

    parser.add_argument('--id', nargs="?", type=str, default=None, help="specific collection? ie ftimperialcol")

    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

