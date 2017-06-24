import os
import sickle
import boto
import datetime
import requests
from time import sleep
from time import time
from util import elapsed
import zlib
import re
import json
import argparse
from util import JSONSerializerPython2
from elasticsearch import Elasticsearch, RequestsHttpConnection, compat, exceptions
from elasticsearch.helpers import parallel_bulk
from elasticsearch.helpers import bulk
import random

from old_update_base_in_elastic import find_fulltext_for_base_hits



# set up elasticsearch
INDEX_NAME = "base"
TYPE_NAME = "record"


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
            # print u"Record is missing required key '{}'!".format(k)
            return False

    if record["oa"] == 0:
        print u"record {} is closed access. skipping.".format(record["id"])
        return False

    return True


def is_good_file(filename):
    return filename.startswith("base_dc_dump") and filename.endswith(".gz")

def set_up_elastic(url):
    if not url:
        url = os.getenv("BASE_URL")
    es = Elasticsearch(url,
                       serializer=JSONSerializerPython2(),
                       retry_on_timeout=True,
                       max_retries=100)

    # if es.indices.exists(INDEX_NAME):
    #     print("deleting '%s' index..." % (INDEX_NAME))
    #     res = es.indices.delete(index = INDEX_NAME)
    #     print(" response: '%s'" % (res))
    #
    # print u"creating index"
    # res = es.indices.create(index=INDEX_NAME)
    return es



def make_record_for_es(record):
    action_record = record
    action_record.update({
        '_op_type': 'index',
        '_index': INDEX_NAME,
        '_type': TYPE_NAME,
        '_id': record["id"]})
    return action_record

def save_records_in_es(es, records_to_save, threads, chunk_size):
    start_time = time()

    # have to do call parallel_bulk in a for loop because is parallel_bulk is a generator so you have to call it to
    # have it do the work.  see https://discuss.elastic.co/t/helpers-parallel-bulk-in-python-not-working/39498
    if threads > 1:
        for success, info in parallel_bulk(es,
                                           actions=records_to_save,
                                           refresh=False,
                                           request_timeout=600,
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

def oaipmh_to_elastic(start_date=None, end_date=None, today=None, threads=0, chunk_size=None, url=None):
    es = set_up_elastic(url)
    proxy_url = os.getenv("STATIC_IP_PROXY")
    proxies = {"https": proxy_url, "http": proxy_url}
    base_sickle = sickle.Sickle("http://oai.base-search.net/oai", proxies=proxies)

    if today:
        end_date = datetime.date.today().isoformat()
        start_date = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    args = {'metadataPrefix': 'base_dc', 'from': start_date}
    if end_date:
        args["until"] = end_date
    oai_records = base_sickle.ListRecords(ignore_deleted=True, **args)

    hits = []
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
            hits.append(record)
            print ":",
        else:
            print ".",

        if len(hits) >= 5:
            records_to_save = find_fulltext_for_base_hits(hits)
            save_records_in_es(es, records_to_save, threads, chunk_size)
            print "last record saved:", records_to_save[-1]
            print "last timestamp saved:", records_to_save[-1]["doc"]["base_timestamp"]
            hits = []

        oai_record = safe_get_next_record(oai_records)

    # make sure to get the last ones
    if hits:
        records_to_save = find_fulltext_for_base_hits(hits)
        save_records_in_es(es, records_to_save, threads, chunk_size)
        print "last record saved:", hits[-1]



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    function = oaipmh_to_elastic
    parser.add_argument('--start_date', type=str, help="first date to pull stuff from oai-pmh (example: --start_date 2016-11-10")
    parser.add_argument('--end_date', type=str, help="last date to pull stuff from oai-pmh (example: --end_date 2016-11-10")
    parser.add_argument('--start_scroll_date', type=str, help="first date to pull stuff from oai-pmh (example: --start_scroll_date 2016-11-10")

    parser.add_argument('--today', action="store_true", default=False, help="use if you want to pull in base records from last 2 days")

    # good for both of them
    parser.add_argument('--url', nargs="?", type=str, help="elasticsearch connect url (example: --url http://70f78ABCD.us-west-2.aws.found.io:9200")
    parser.add_argument('--threads', nargs="?", type=int, help="how many threads if multi")
    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

