import os
import sickle
import boto
import datetime
import requests
from time import sleep
from time import time
from util import elapsed
import logging
import zlib
import re
import json
import argparse
from elasticsearch import Elasticsearch, RequestsHttpConnection, compat, exceptions
from elasticsearch.helpers import parallel_bulk
from elasticsearch.helpers import bulk
from elasticsearch.helpers import scan
import random

import oa_local
from util import JSONSerializerPython2


# set up elasticsearch
INDEX_NAME = "base"
TYPE_NAME = "record"


libraries_to_mum = [
    "requests.packages.urllib3",
    "requests_oauthlib",
    "stripe",
    "oauthlib",
    "boto",
    "newrelic",
    "RateLimiter",
    "elasticsearch",
    "urllib3"
]

for a_library in libraries_to_mum:
    the_logger = logging.getLogger(a_library)
    the_logger.setLevel(logging.WARNING)
    the_logger.propagate = True


class MissingTagException(Exception):
    pass


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





def save_records_in_es(es, records_to_save, threads, chunk_size):
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
    print u"done sending {} records to elastic in {}s".format(len(records_to_save), elapsed(start_time, 4))



def get_urls_from_our_base_doc(doc):
    response = []

    if "urls" in doc:
        # pmc can only add pmc urls.  otherwise has junk about dois that aren't actually open.
        if u"PubMed Central (PMC)" in doc["sources"]:
            for url in doc["urls"]:
                if "/pmc/" in url and url != "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
                    response += [url]
        else:
            response += doc["urls"]

    # filter out all the urls that go straight to publisher pages from base response
    response = [url for url in response if u"doi.org/" not in url]

    # oxford IR doesn't return URLS, instead it returns IDs from which we can build URLs
    # example: https://www.base-search.net/Record/5c1cf4038958134de9700b6144ae6ff9e78df91d3f8bbf7902cb3066512f6443/
    if "sources" in doc and "Oxford University Research Archive (ORA)" in doc["sources"]:
        if "relations" in doc:
            for relation in doc["relations"]:
                if relation.startswith("uuid"):
                    response += [u"https://ora.ox.ac.uk/objects/{}".format(relation)]

    return response


def update_base2s(first=None, last=None, url=None, threads=0, randomize=False, chunk_size=None):
    es = set_up_elastic(url)
    total_start = time()

    query = {
    "query" : {
        "bool" : {
            "filter" : [{ "term" : { "oa" : 1 }},
                        { "not": {"exists" : {"field": "fulltext_updated"}}}]
            }
        }
    }

    scan_iter = scan(es, index=INDEX_NAME, query=query)
    result = scan_iter.next()

    records_to_save = []
    i = 0
    while result:

        # print ".",
        current_record = result["_source"]
        doc = {}
        doc["fulltext_urls"] = get_urls_from_our_base_doc(current_record)
        if "license" in current_record:
            license = oa_local.find_normalized_license(format(current_record["license"]))
            if license and license != "unknown":
                doc["fulltext_license"] = license
            else:
                doc["fulltext_license"] = None  # overwrite in case something was there before
        doc["fulltext_updated"] = datetime.datetime.utcnow().isoformat()

        action = {"doc": doc}
        action["_id"] = result["_id"]
        action['_op_type'] = 'update'
        action["_type"] = TYPE_NAME
        action['_index'] = INDEX_NAME
        records_to_save.append(action)

        if len(records_to_save) >= 1000:
            print "\n{}s to do {}.  now more saving.".format(elapsed(total_start, 2), i)
            save_records_in_es(es, records_to_save, threads, chunk_size)
            records_to_save = []
            print "done saving\n"

        result = scan_iter.next()
        i += 1

    # make sure to get the last ones
    save_records_in_es(es, records_to_save, 1, chunk_size)




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")


    # just for updating lots
    function = update_base2s
    parser.add_argument('--url', nargs="?", type=str, help="elasticsearch connect url (example: --url http://70f78ABCD.us-west-2.aws.found.io:9200")
    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first ListRecords.14461")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last ListRecords.14461)")
    parser.add_argument('--randomize', dest='randomize', action='store_true', help="pull random files from AWS")

    # good for both of them
    parser.add_argument('--threads', nargs="?", type=int, help="how many threads if multi")
    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

