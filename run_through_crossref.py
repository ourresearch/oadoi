import os
from time import time
from util import elapsed
import logging
import sys
import random
from elasticsearch import Elasticsearch, RequestsHttpConnection, compat, exceptions
from sqlalchemy import sql

from util import JSONSerializerPython2
from app import db

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



def set_up_elastic(url):
    if not url:
        url = os.getenv("CROSSREF_ES_URL")
    es = Elasticsearch(url,
                       serializer=JSONSerializerPython2(),
                       retry_on_timeout=True,
                       max_retries=100)
    return es





query = {
  "_source": [
    "id"
  ],
  "size": 1000,
  "from": int(random.random()*8999),
  "query": {
    "bool": {
      "must": {
        "exists": {
          "field": "title"
        }
      }
    }
  }
}




def do_a_loop(first=None, last=None, url=None, threads=0, chunk_size=None):
    es = set_up_elastic(url)
    loop_start = time()
    total_dois = 0

    # from https://gist.github.com/drorata/146ce50807d16fd4a6aa
    # Initialize the scroll
    page = es.search(
      index = INDEX_NAME,
      doc_type = TYPE_NAME,
      scroll = '2m',
      size = 1000,
      body = query)
    scroll_id = page['_scroll_id']
    scroll_size = page['hits']['total']

      # Start scrolling
    while (scroll_size > 0):
        print "Scrolling... _scroll_id:{}".format(scroll_id)
        page = es.scroll(scroll_id = scroll_id, scroll = '2m')
        dois = page["hits"]
        # Update the scroll ID
        scroll_id = page['_scroll_id']
        # Get the number of results that we returned in the last scroll
        scroll_size = len(page['hits']['hits'])
        print "scroll size: " + str(scroll_size)
        # Do something with the obtained page


        # decide if should stop looping after this
        if not page['hits']['hits']:
            sys.exit()

        dois = []
        for crossref_hit in page['hits']['hits']:
            crossref_hit_doc = crossref_hit["_source"]
            doi = crossref_hit["_id"]
            dois.append(doi.lower())

        print "** {} seconds to do {}\n".format(elapsed(loop_start, 2), len(dois))

        dois_insert_string = ",".join(["('{}')".format(doi) for doi in dois])
        insert_statement = u"""insert into cached (id) values {};""".format(dois_insert_string)
        rows = db.engine.execute(sql.text(insert_statement))
        print "some dois", dois[0:10]
        total_dois += len(dois)


    return total_dois



if __name__ == "__main__":
    # just for updating lots
    dois = do_a_loop()
    while dois:
        dois = do_a_loop()
        print dois

