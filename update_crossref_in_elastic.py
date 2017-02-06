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
import sys
import random
import argparse
from elasticsearch import Elasticsearch, RequestsHttpConnection, compat, exceptions
from elasticsearch.helpers import parallel_bulk
from elasticsearch.helpers import bulk
from elasticsearch.helpers import scan
from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Pool
from HTMLParser import HTMLParser


import oa_local
from oa_base import get_urls_from_our_base_doc
from publication import call_targets_in_parallel
from webpage import WebpageInUnknownRepo
from util import JSONSerializerPython2


# set up elasticsearch
INDEX_NAME = "crossref"
TYPE_NAME = "crosserf_api"  #was typo on insert, so still running with it



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
        url = os.getenv("CROSSREF_ES_URL")
    es = Elasticsearch(url,
                       serializer=JSONSerializerPython2(),
                       retry_on_timeout=True,
                       max_retries=100)
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
    print u"done sending {} records to elastic in {} seconds".format(len(records_to_save), elapsed(start_time, 4))
    print u"most recent record: {}".format(records_to_save[0])


# remaning: 84,778,593  ata 9:20pm sunday
# 84,474,078 at 9:28pm
# 82,890,743 at 9:55pm

query = {
  "_source": [
    "title",
    "id"
  ],
  "size": 1000,
  "from": int(random.random()*8999),
  "query": {
    "bool": {
      "must_not": {
        "exists": {
          "field": "random"
        }
      }
    }
  }
}



class CrossrefResult(object):
    def __init__(self, id, doc):
        self.id = id
        self.doc = doc


    def make_action_record(self):
        update_doc = {
            "random": random.random()
        }

        action = {"doc": update_doc}
        action["_id"] = self.id
        action['_op_type'] = 'update'
        action["_type"] = TYPE_NAME
        action['_index'] = INDEX_NAME
        # print "\n", action
        return action


def do_a_loop(first=None, last=None, url=None, threads=0, chunk_size=None):
    es = set_up_elastic(url)
    loop_start = time()
    results = es.search(index=INDEX_NAME, body=query, request_timeout=10000)
    # print u"search body:\n{}".format(query)
    print u"took {} seconds to search ES. remaining: {:,}".format(
        elapsed(loop_start, 2), results["hits"]["total"])
    records_to_save = []

    # decide if should stop looping after this
    if not results['hits']['hits']:
        sys.exit()

    crossref_results = []
    for crossref_hit in results['hits']['hits']:
        crossref_hit_doc = crossref_hit["_source"]
        crossref_results.append(CrossrefResult(crossref_hit["_id"], crossref_hit_doc))

    for crossref_result in crossref_results:
        records_to_save.append(crossref_result.make_action_record())

    # print "records_to_save", records_to_save
    print "starting saving"
    save_records_in_es(es, records_to_save, threads, chunk_size)
    print "** {} seconds to do {}\n".format(elapsed(loop_start, 2), len(crossref_results))


def update_everything():
    has_more_records = True
    while has_more_records:
        pool_time = time()
        my_process = Process(target=do_a_loop)
        my_process.daemon = True
        my_process.start()
        my_process.join()
        my_process.terminate()
        print u"waited {} seconds for do_a_loop".format(elapsed(pool_time, 2))



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")


    # just for updating lots
    function = update_everything
    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

