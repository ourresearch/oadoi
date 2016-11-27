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
INDEX_NAME = "base"
TYPE_NAME = "record"


def call_scrape(base_result_object):
    try:
        base_result_object.scrape_for_fulltext()
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print u"in call_scrape, got Exception: {}".format(e)
        base_result_object.error = True

    # do this to free memory, ala http://stackoverflow.com/a/8823200/596939.
    # has to be done *inside* the thread to work
    sys.exc_clear()
    return base_result_object


def run_scrape_in_parallel(base_result_objects):
    pool = Pool()
    pool_time = time()
    results = pool.map(call_scrape, base_result_objects)
    pool.close()
    pool.join()
    print u"waited {}s for pool".format(elapsed(pool_time, 2))
    return results




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
    print records_to_save[0]



# chosen to help randomize the documents
query_strings = [
    "patel liu smith anderson harris long",
    "park singh li miller garcia campbell parker",
    "tran kaur ho stevens cole cook lopez young",
    "lam sharma peng bah green clark hall king wilson martin",
    "zhang persaud martinez davis lewis allen hernandez carter",
    "yang wilson taylor roberts wong baker perez bell gray ward",
    "campbell leung howard richardson wood ford diaz graham henry",
    "wang chang rice daniels hunt moore anderson",
    "le kim lin allen wright turner ross butler west banks"
    ]

query = {
  "_source": [
    "title",
    "urls",
    "license",
    "sources",
    "id"
  ],
  "size": 100,
  "from": int(random.random()*9899),
  "query": {
    "bool": {
      "must_not": {
        "exists": {
          "field": "fulltext_last_updated"
        }
      },
      "must": {
        "term": {
          "oa": 2
        }
      },
      "should": {
        "match": {
            "_all": random.choice(query_strings)
        }
      }
    }
  }
}


class BaseResult(object):
    def __init__(self, doc):
        self.doc = doc
        self.fulltext_last_updated = datetime.datetime.utcnow().isoformat()
        self.fulltext_url_dicts = []
        self.license = None
        self.set_webpages()

    def scrape_for_fulltext(self):
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
            self.license = oa_local.find_normalized_license(self.doc["license"])

        for my_webpage in self.open_webpages:
            if my_webpage.has_fulltext_url:
                self.fulltext_url_dicts += [{"free_pdf_url": my_webpage.scraped_pdf_url, "pdf_landing_page": my_webpage.url}]
                if not self.license or self.license == "unknown":
                    self.license = my_webpage.scraped_license
            else:
                print "{} has no fulltext url alas".format(my_webpage)

        if self.license == "unknown":
            self.license = None


    def make_action_record(self):
        update_doc = {
                        "fulltext_last_updated": self.fulltext_last_updated,
                        "fulltext_url_dicts": self.fulltext_url_dicts,
                        "fulltext_license": self.license,
                        "fulltext_updated": None,
                        "random": random.random()
        }

        action = {"doc": update_doc}
        action["_id"] = self.doc["id"]
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
    print u"took {}s to search ES".format(elapsed(loop_start, 2))
    records_to_save = []

    # decide if should stop looping after this
    if not results['hits']['hits']:
        sys.exit()

    base_results = []
    for base_hit in results['hits']['hits']:
        base_hit_doc = base_hit["_source"]
        base_results.append(BaseResult(base_hit_doc))

    scrape_start = time()

    # base_results_scraped = run_scrape_in_parallel(base_results)

    targets = [base_result.scrape_for_fulltext for base_result in base_results]
    call_targets_in_parallel(targets)

    print u"scraping {} webpages took {}s".format(len(base_results), elapsed(scrape_start, 2))

    for base_result in base_results:
        base_result.set_fulltext_urls()
        records_to_save.append(base_result.make_action_record())

    # print "records_to_save", records_to_save
    print "starting saving"
    save_records_in_es(es, records_to_save, threads, chunk_size)
    print "** {}s to do {}\n".format(elapsed(loop_start, 2), len(base_results))




def update_base2s(first=None, last=None, url=None, threads=0, chunk_size=None):
    has_more_records = True
    while has_more_records:
        pool_time = time()
        my_process = Process(target=do_a_loop)
        my_process.daemon = True
        my_process.start()
        my_process.join()
        my_process.terminate()
        print u"waited {}s for do_a_loop".format(elapsed(pool_time, 2))


def update_base1s(first=None, last=None, url=None, threads=0, chunk_size=None):
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

    # good for both of them
    parser.add_argument('--threads', nargs="?", type=int, help="how many threads if multi")
    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

