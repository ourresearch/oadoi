import os
import sickle
import boto
import datetime
import requests
from time import sleep
from time import time
import re
import argparse
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import logger
from util import safe_commit
from util import elapsed
from util import is_doi_url
from util import clean_doi


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


def is_complete(record):
    if not record.id:
        return False
    if not record.title:
        return False
    if not record.urls:
        return False

    if record.oa == "0":
        logger.info(u"record {} is closed access. skipping.".format(record["id"]))
        return False

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
    source = db.Column(db.Text)
    id = db.Column(db.Text, primary_key=True)
    # doi = db.Column(db.Text, db.ForeignKey('crossref.id'))
    doi = db.Column(db.Text)
    record_timestamp = db.Column(db.DateTime)
    api_raw = db.Column(JSONB)
    title = db.Column(db.Text)
    license = db.Column(db.Text)
    oa = db.Column(db.Text)
    urls = db.Column(JSONB)
    authors = db.Column(JSONB)
    relations = db.Column(JSONB)
    sources = db.Column(JSONB)
    updated = db.Column(db.DateTime)

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


    my_sickle = sickle.Sickle(url, proxies=proxies)
    print "got my_sickle"

    if today:
        last = datetime.date.today().isoformat()
        first = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    args['from'] = first
    if last:
        args["until"] = last

    oai_records = my_sickle.ListRecords(ignore_deleted=True, **args)
    print "got oa_records"

    records_to_save = []
    oai_pmh_input_record = safe_get_next_record(oai_records)
    while oai_pmh_input_record:
        pmh_record = PmhRecord()

        pmh_record.id = oai_pmh_input_record.header.identifier
        pmh_record.api_raw = oai_pmh_input_record.raw
        pmh_record.record_timestamp = oai_pmh_input_record.header.datestamp
        pmh_record.title = oai_tag_match("title", oai_pmh_input_record)
        pmh_record.authors = oai_tag_match("creator", oai_pmh_input_record, return_list=True)
        pmh_record.oa = oai_tag_match("oa", oai_pmh_input_record)
        pmh_record.urls = oai_tag_match("identifier", oai_pmh_input_record, return_list=True)
        for fulltext_url in pmh_record.urls:
            if is_doi_url(fulltext_url):
                pmh_record.doi = clean_doi(fulltext_url)

        pmh_record.license = oai_tag_match("rights", oai_pmh_input_record)
        pmh_record.relations = oai_tag_match("relation", oai_pmh_input_record, return_list=True)
        pmh_record.sources = oai_tag_match("collname", oai_pmh_input_record, return_list=True)
        pmh_record.source = url

        # print pmh_record

        if is_complete(pmh_record):
            db.session.merge(pmh_record)
            records_to_save.append(pmh_record)
            logger.info(u":")

        if len(records_to_save) >= chunk_size:
            logger.info(u"last record saved: {}".format(records_to_save[-1]))
            logger.info(u"committing")
            safe_commit(db)
            records_to_save = []

        oai_pmh_input_record = safe_get_next_record(oai_records)

    # make sure to get the last ones
    logger.info(u"saving last ones")
    safe_commit(db)
    logger.info(u"done everything")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = oaipmh_to_db
    parser.add_argument('--first', type=str, help="first date to pull stuff from oai-pmh (example: --start_date 2016-11-10")
    parser.add_argument('--last', type=str, help="last date to pull stuff from oai-pmh (example: --end_date 2016-11-10")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in base records from last 2 days")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=10, help="how many rows before a db commit")

    # parser.add_argument('--url', nargs="?", type=str, default="http://export.arxiv.org/oai2", help="oai-pmh url")
    parser.add_argument('--url', nargs="?", type=str, default="http://citeseerx.ist.psu.edu/oai2", help="oai-pmh url")

    parsed = parser.parse_args()

    logger.info(u"calling {} with these args: {}".format(function.__name__, vars(parsed)))
    function(**vars(parsed))

