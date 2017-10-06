import os
import sickle
import boto
import datetime
import requests
from time import sleep
from time import time
import re
import argparse

from app import db
from app import logger
from util import safe_commit
from util import elapsed
from util import is_doi_url
from util import clean_doi
from publication import Base
from publication import call_targets_in_parallel


class MissingTagException(Exception):
    pass


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

    # if record["oa"] == 0:
    #     logger.info(u"record {} is closed access. skipping.".format(record["id"]))
    #     return False

    return True



def safe_get_next_record(records):
    try:
        next_record = records.next()
    except requests.exceptions.HTTPError:
        logger.info(u"HTTPError exception!  skipping")
        return safe_get_next_record(records)
    except (KeyboardInterrupt, SystemExit):
        # done
        return None
    except Exception:
        raise
        logger.info(u"misc exception!  skipping")
        return safe_get_next_record(records)
    return next_record



class PmhRecord(db.Model):
    id = db.Column(db.Text, primary_key=True)
    record_id = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'))
    error = db.Column(db.Text)
    updated = db.Column(db.DateTime)
    record_timestamp = db.Column(db.DateTime)
    title = db.Column(db.Text)
    license = db.Column(db.Text)
    oa = db.Column(db.Text)
    urls = db.Column(JSONB)
    authors = db.Column(JSONB)
    relations = db.Column(JSONB)
    sources = db.Column(JSONB)

    def __init__(self, **kwargs):
        self.updated = datetime.datetime.utcnow().isoformat()
        super(self.__class__, self).__init__(**kwargs)


def oaipmh_to_db(first=None,
                 last=None,
                 today=None,
                 chunk_size=10,
                 url=None):

    args = {}
    if not url:
        # do base
        url="http://oai.base-search.net/oai"
        args['metadataPrefix'] = 'base_dc'
        proxy_url = os.getenv("STATIC_IP_PROXY")
        proxies = {"https": proxy_url, "http": proxy_url}
    else:
        args['metadataPrefix'] = 'oai_dc'
        proxies = {}


    base_sickle = sickle.Sickle(url, proxies=proxies)

    if today:
        last = datetime.date.today().isoformat()
        first = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    args['from'] = first
    if last:
        args["until"] = last

    oai_records = base_sickle.ListRecords(ignore_deleted=True, **args)

    base_objects = []
    pmh_record_dict = safe_get_next_record(oai_records)
    while pmh_record_dict:
        pmh_record = PmhRecord()

        # @todo
        # use is_complete here to only save pmhrecords if they have a title etc

        pmh_record.id = pmh_record_dict.header.identifier
        pmh_record.record_timestamp = pmh_record_dict.header.datestamp

        pmh_record.title = oai_tag_match("title", pmh_record_dict)
        pmh_record.license = oai_tag_match("rights", pmh_record_dict)
        pmh_record.oa = oai_tag_match("oa", pmh_record_dict)
        pmh_record.urls = oai_tag_match("identifier", pmh_record_dict, return_list=True)
        pmh_record.authors = oai_tag_match("creator", pmh_record_dict, return_list=True)
        pmh_record.relations = oai_tag_match("relation", pmh_record_dict, return_list=True)
        pmh_record.sources = oai_tag_match("collname", pmh_record_dict, return_list=True)

        pmh_record.id=record["id"]
        pmh_record.body=record_body
        pmh_record.doi=record_doi
        pmh_record.oaipmh_url = url

        for url in record["urls"]:
            if is_doi_url(url):
                record_doi = clean_doi(url)

        print pmh_record

        db.session.merge(pmh_record)
        base_objects.append(pmh_record)
        logger.info(u":")

        if len(base_objects) >= chunk_size:
            logger.info(u"last record saved: {}".format(base_objects[-1]))
            logger.info(u"committing")
            safe_commit(db)
            base_objects = []

        pmh_record_dict = safe_get_next_record(oai_records)

    # make sure to get the last ones
    logger.info(u"saving last ones")
    # safe_commit(db)
    logger.info(u"done everything")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = oaipmh_to_db
    parser.add_argument('--first', type=str, help="first date to pull stuff from oai-pmh (example: --start_date 2016-11-10")
    parser.add_argument('--last', type=str, help="last date to pull stuff from oai-pmh (example: --end_date 2016-11-10")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in base records from last 2 days")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=10, help="how many rows before a db commit")
    parser.add_argument('--collection', nargs="?", type=str, default=None, help="specific collection? ie ftimperialcol")

    parser.add_argument('--id', nargs="?", type=str, default=None, help="specific collection? ie ftimperialcol")

    parser.add_argument('--url', nargs="?", type=str, default=None, help="oai-pmh url")

    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

