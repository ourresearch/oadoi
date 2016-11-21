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
from elasticsearch import Elasticsearch, RequestsHttpConnection, serializer, compat, exceptions
from elasticsearch.helpers import parallel_bulk
from elasticsearch.helpers import bulk
import random

# set up elasticsearch
INDEX_NAME = "crossref"
TYPE_NAME = "crosserf_api"


# data from https://archive.org/details/crossref_doi_metadata
# To update the dump, use the public API with deep paging:
# http://api.crossref.org/works?filter=from-update-date:2014-04-01&cursor=*
# The documentation for this feature is available at:
# https://github.com/CrossRef/rest-api-doc/blob/master/rest_api.md#deep-paging-with-cursors


# from https://github.com/elastic/elasticsearch-py/issues/374
# to work around unicode problem
class JSONSerializerPython2(serializer.JSONSerializer):
    """Override elasticsearch library serializer to ensure it encodes utf characters during json dump.
    See original at: https://github.com/elastic/elasticsearch-py/blob/master/elasticsearch/serializer.py#L42
    A description of how ensure_ascii encodes unicode characters to ensure they can be sent across the wire
    as ascii can be found here: https://docs.python.org/2/library/json.html#basic-usage
    """
    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, compat.string_types):
            return data
        try:
            return json.dumps(data, default=self.default, ensure_ascii=True)
        except (ValueError, TypeError) as e:
            raise exceptions.SerializationError(data, e)



def is_good_file(filename):
    return "chunk_" in filename

def set_up_elastic(url):
    if not url:
        url = os.getenv("CROSSREF_ES_URL")
    es = Elasticsearch(url,
                       serializer=JSONSerializerPython2(),
                       retry_on_timeout=True,
                       max_retries=100)

    if es.indices.exists(INDEX_NAME):
        print("deleting '%s' index..." % (INDEX_NAME))
        res = es.indices.delete(index = INDEX_NAME)
        print(" response: '%s'" % (res))

    # print u"creating index"
    # res = es.indices.create(index=INDEX_NAME, ignore=400, body=mapping)
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
    print "starting save"
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


def get_citeproc_date(year=0, month=1, day=1):
    return datetime.datetime(year, month, day).isoformat()

def s3_to_elastic(first=None, last=None, url=None, threads=0, randomize=False, chunk_size=None):
    es = set_up_elastic(url)

    # set up aws s3 connection
    conn = boto.connect_s3(
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    my_bucket = conn.get_bucket('impactstory-crossref')

    i = 0
    records_to_save = []

    keys = my_bucket.list()[0:2]
    print "keys:", keys

    for key in keys:
        if not is_good_file(key.name):
            continue

        key_filename = key.name.split("/")[-1]  # get rid of all subfolders

        if first and key_filename < first:
            continue

        if last and key_filename > last:
            continue

        # if i >= 2:
        #     return

        print "getting this key...", key.name
        contents = key.get_contents_as_string()

        # fd = open("/Users/hpiwowar/Downloads/chunk_1606", "r")
        # contents = fd.read()

        for line in contents.split("\n"):
            if not line:
                continue

            (doi, data_date, data_text) = line.split("\t")
            data = json.loads(data_text)

            # make sure this is unanalyzed
            record = {}
            record["id"] = doi

            simple_fields = [
                "publisher",
                "subject",
                "link",
                "license",
                "funder",
                "type",
                "update-to",
                "clinical-trial-number",
                "issn",
                "isbn",
                "alternative-id"
            ]

            for field in simple_fields:
                if field in data:
                    record[field.lower()] = data[field]

            try:
                record["title"] = re.sub(u"\s+", u" ", data["title"][0])
            except (AttributeError, TypeError, KeyError, IndexError):
                pass

            if "container-title" in data:
                try:
                    record["journal"] = data["container-title"][-1]
                except (IndexError, TypeError):
                    record["journal"] = data["container-title"]
                record["all_journals"] = data["container-title"]

            if "author" in data:
                record["authors"] = data["author"]
                try:
                    first_author_lastname = data["author"][0]["family"]
                except (AttributeError, TypeError, KeyError):
                    pass

            if "issued" in data:
                # record["issued_raw"] = data["issued"]
                try:
                    if "raw" in data["issued"]:
                        record["year"] = int(data["issued"]["raw"])
                    elif "date-parts" in data["issued"]:
                        record["year"] = int(data["issued"]["date-parts"][0][0])
                        date_parts = data["issued"]["date-parts"][0]
                        record["pubdate"] = get_citeproc_date(*date_parts)
                except (IndexError, TypeError):
                    pass

            record["added_timestamp"] = datetime.datetime.utcnow().isoformat()

            # print record
            print ".",

            action_record = make_record_for_es(record)
            records_to_save.append(action_record)

        i += 1
        # if len(records_to_save) >= 1:  #10000
        #     save_records_in_es(es, records_to_save, threads, chunk_size)
        #     records_to_save = []
        print "at bottom of loop"

    # make sure to get the last ones
    # save_records_in_es(es, records_to_save, 1, chunk_size)
    print "done everything"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    function = s3_to_elastic
    parser.add_argument('--url', nargs="?", type=str, help="elasticsearch connect url (example: --url http://70f78ABCD.us-west-2.aws.found.io:9200")
    parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first ListRecords.14461")
    parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last ListRecords.14461)")

    parser.add_argument('--threads', nargs="?", type=int, help="how many threads if multi")
    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

