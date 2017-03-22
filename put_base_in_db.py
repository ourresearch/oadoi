import os
import sickle
import boto
import datetime
import requests
from time import sleep
from time import time
import zlib
import re
import json
import argparse
import random
from sqlalchemy.dialects.postgresql import JSONB

from app import db
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


class BaseResult(object):
    def __init__(self, base_obj):
        self.doc = base_obj.doc
        self.fulltext_last_updated = datetime.datetime.utcnow().isoformat()
        self.fulltext_url_dicts = []
        self.license = None
        self.set_webpages()


    def scrape_for_fulltext(self):
        if self.doc["oa"] == 1:
            return

        response_webpages = []

        found_open_fulltext = False
        for my_webpage in self.webpages:
            if not found_open_fulltext:
                my_webpage.scrape_for_fulltext_link()
                if my_webpage.has_fulltext_url:
                    print u"** found an open version! {}".format(my_webpage.fulltext_url)
                    found_open_fulltext = True
                    response_webpages.append(my_webpage)

        self.open_webpages = response_webpages
        sys.exc_clear()  # someone on the internet said this would fix All The Memory Problems. has to be in the thread.
        return self

    def set_webpages(self):
        self.open_webpages = []
        self.webpages = []
        for url in get_urls_from_our_base_doc(self.doc):
            my_webpage = WebpageInUnknownRepo(url=url)
            self.webpages.append(my_webpage)


    def set_fulltext_urls(self):

        # first set license if there is one originally.  overwrite it later if scraped a better one.
        if "license" in self.doc and self.doc["license"]:
            self.license = find_normalized_license(self.doc["license"])

        for my_webpage in self.open_webpages:
            if my_webpage.has_fulltext_url:
                response = {}
                self.fulltext_url_dicts += [{"free_pdf_url": my_webpage.scraped_pdf_url, "pdf_landing_page": my_webpage.url}]
                if not self.license or self.license == "unknown":
                    self.license = my_webpage.scraped_license
            else:
                print "{} has no fulltext url alas".format(my_webpage)

        if self.license == "unknown":
            self.license = None


    def make_action_record(self):

        doc = self.doc

        update_fields = {
            "random": random.random(),
            "fulltext_last_updated": self.fulltext_last_updated,
            "fulltext_url_dicts": self.fulltext_url_dicts,
            "fulltext_license": self.license,
        }

        doc.update(update_fields)
        action = {"doc": doc}
        action["_id"] = self.doc["id"]
        # print "\n", action
        return action

def find_fulltext_for_base_hits(base_objects):
    records_to_save = []
    base_results = []

    for base_hit in base_objects:
        base_results.append(BaseResult(base_hit))

    scrape_start = time()

    targets = [base_result.scrape_for_fulltext for base_result in base_results]
    call_targets_in_parallel(targets)
    print u"scraping {} webpages took {} seconds".format(len(base_results), elapsed(scrape_start, 2))

    for base_result in base_results:
        base_result.set_fulltext_urls()
        records_to_save.append(base_result.make_action_record())

    return records_to_save


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
            # print u"Record is missing required key '{}'!".format(k)
            return False

    if record["oa"] == 0:
        print u"record {} is closed access. skipping.".format(record["id"])
        return False

    return True


def is_good_file(filename):
    return filename.startswith("base_dc_dump") and filename.endswith(".gz")





def make_record_for_es(record):
    action_record = record
    action_record.update({
        '_op_type': 'index',
        '_index': INDEX_NAME,
        '_type': TYPE_NAME,
        '_id': record["id"]})
    return action_record

def save_records_in_db(records_to_save, threads, chunk_size):
    start_time = time()

    # have to do call parallel_bulk in a for loop because is parallel_bulk is a generator so you have to call it to
    # have it do the work.  see https://discuss.elastic.co/t/helpers-parallel-bulk-in-python-not-working/39498
    if threads > 1:
        for success, info in parallel_bulk(es,
                                           actions=records_to_save,
                                           refresh=False,
                                           request_timeout=60,
                                           thread_count=threads,
                                           chunk_size=chunk_size):
            if not success:
                print('A document failed:', info)
    else:
        for success_info in bulk(es, actions=records_to_save, refresh=False, request_timeout=60, chunk_size=chunk_size):
            pass
    print u"done sending {} records to elastic in {} seconds".format(len(records_to_save), elapsed(start_time, 4))


def safe_get_next_record(records):
    try:
        next_record = records.next()
    except requests.exceptions.HTTPError:
        print "HTTPError exception!  skipping"
        return safe_get_next_record(records)
    except (KeyboardInterrupt, SystemExit):
        # done
        return None
    except Exception:
        raise
        print "misc exception!  skipping"
        return safe_get_next_record(records)
    return next_record




def oaipmh_to_db(first=None, last=None, today=None, threads=0, chunk_size=None, url=None):
    proxy_url = os.getenv("STATIC_IP_PROXY")
    proxies = {"https": proxy_url, "http": proxy_url}
    base_sickle = sickle.Sickle("http://oai.base-search.net/oai", proxies=proxies)

    if today:
        last = datetime.date.today().isoformat()
        first = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    args = {'metadataPrefix': 'base_dc', 'from': first}
    if last:
        args["until"] = last
    oai_records = base_sickle.ListRecords(ignore_deleted=True, **args)

    base_objects = []
    print 'chunk_size', chunk_size
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
            print "my_base:", my_base
            db.session.merge(my_base)
            base_objects.append(my_base)
            print ":",
        else:
            print ".",

        if len(base_objects) >= 10:
            records_to_save = find_fulltext_for_base_hits(base_objects)
            safe_commit(db)
            print "last record saved:", records_to_save[-1]
            print "last timestamp saved:", records_to_save[-1]["doc"]["base_timestamp"]
            base_objects = []

        oai_record = safe_get_next_record(oai_records)

    # make sure to get the last ones
    print "saving last ones"
    records_to_save = find_fulltext_for_base_hits(base_objects)
    safe_commit(db)
    print "done everything"



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = oaipmh_to_db
    parser.add_argument('--first', type=str, help="first date to pull stuff from oai-pmh (example: --start_date 2016-11-10")
    parser.add_argument('--last', type=str, help="last date to pull stuff from oai-pmh (example: --end_date 2016-11-10")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in base records from last 2 days")

    # good for both of them
    parser.add_argument('--url', nargs="?", type=str, help="elasticsearch connect url (example: --url http://70f78ABCD.us-west-2.aws.found.io:9200")
    parser.add_argument('--threads', nargs="?", type=int, help="how many threads if multi")
    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

