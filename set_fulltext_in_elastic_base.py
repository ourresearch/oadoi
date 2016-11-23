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
INDEX_NAME = "base"
TYPE_NAME = "record"

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

# from https://gist.github.com/drorata/146ce50807d16fd4a6aa
# Initialize the scroll
page = es.search(
  index = 'yourIndex',
  doc_type = 'yourType',
  scroll = '2m',
  search_type = 'scan',
  size = 1000,
  body = {
    # Your query's body
    })
  sid = page['_scroll_id']
  scroll_size = page['hits']['total']

  # Start scrolling
  while (scroll_size > 0):
    print "Scrolling..."
    page = es.scroll(scroll_id = sid, scroll = '2m')
    # Update the scroll ID
    sid = page['_scroll_id']
    # Get the number of results that we returned in the last scroll
    scroll_size = len(page['hits']['hits'])
    print "scroll size: " + str(scroll_size)
    # Do something with the obtained page


# curl -XPOST 'localhost:9200/test/type1/1/_update' -d '{
#     "doc" : {
#         "fulltext_urls" : []
#     }
# }'

def make_record_for_es(record):
    action_record = record
    action_record.update({
        '_op_type': 'index',
        '_index': INDEX_NAME,
        '_type': 'record',
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
                                           request_timeout=60,
                                           thread_count=threads,
                                           chunk_size=chunk_size):
            if not success:
                print('A document failed:', info)
    else:
        for success_info in bulk(es, actions=records_to_save, refresh=False, request_timeout=60, chunk_size=chunk_size):
            pass
    print u"done sending {} records to elastic in {}s".format(len(records_to_save), elapsed(start_time, 4))



def s3_to_elastic(first=None, last=None, url=None, threads=0, randomize=False, chunk_size=None):
    es = set_up_elastic(url)

    # set up aws s3 connection
    conn = boto.connect_s3(
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    my_bucket = conn.get_bucket('base-initial')

    i = 0
    records_to_save = []


    if randomize:
        print "randomizing. this takes a while."
        bucket_list = []
        i = 0
        for key in my_bucket.list():
            if is_good_file(key.name):
                bucket_list.append(key)
                if i % 1000 == 0:
                    print "Adding good files to list: ", i
                i += 1

        print "made a list: ", len(bucket_list)
        random.shuffle(bucket_list)

    else:
        bucket_list = my_bucket.list()


    for key in bucket_list:
        # print key.name

        if not is_good_file(key.name):
            continue


        key_filename = key.name.split("/")[1]

        if first and key_filename < first:
            continue

        if last and key_filename > last:
            continue

        # if i >= 2:
        #     break

        print "getting this key...", key.name

        # that second arg is important. see http://stackoverflow.com/a/18319515
        res = zlib.decompress(key.get_contents_as_string(), 16+zlib.MAX_WBITS)

        xml_records = re.findall("<record>.+?</record>", res, re.DOTALL)

        for xml_record in xml_records:
            record = {}
            record["id"] = tag_match("identifier", xml_record)
            record["title"] = tag_match("dc:title", xml_record)
            record["license"] = tag_match("base_dc:rights", xml_record)

            try:
                record["oa"] = int(tag_match("base_dc:oa", xml_record))
            except TypeError:
                record["oa"] = 0

            record["urls"] = tag_match("dc:identifier", xml_record, return_list=True)
            record["authors"] = tag_match("dc:creator", xml_record, return_list=True)
            record["relations"] = tag_match("dc:relation", xml_record, return_list=True)
            record["sources"] = tag_match("base_dc:collname", xml_record, return_list=True)
            record["filename"] = key_filename

            if is_complete(record):
                action_record = make_record_for_es(record)
                records_to_save.append(action_record)

        i += 1
        if len(records_to_save) >= 1:  #10000
            save_records_in_es(es, records_to_save, threads, chunk_size)
            records_to_save = []

    # make sure to get the last ones
    save_records_in_es(es, records_to_save, 1, chunk_size)



# usage
# for record_group in batch(records, 100):
#     for record in record_group:
#         record.metadata
def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


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
        print "misc exception!  skipping"
        return safe_get_next_record(records)
    return next_record

def oaipmh_to_elastic(start_date, end_date=None, threads=0, chunk_size=None, url=None):
    es = set_up_elastic(url)
    proxy_url = os.getenv("STATIC_IP_PROXY")
    proxies = {"https": proxy_url, "http": proxy_url}
    base_sickle = sickle.Sickle("http://oai.base-search.net/oai", proxies=proxies)
    args = {'metadataPrefix': 'base_dc', 'from': start_date}
    if end_date:
        args["until"] = end_date
    oai_records = base_sickle.ListRecords(ignore_deleted=True, **args)

    records_to_save = []
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
            action_record = make_record_for_es(record)
            records_to_save.append(action_record)
            print ":",
        else:
            print ".",

        if len(records_to_save) >= 1000:
            save_records_in_es(es, records_to_save, threads, chunk_size)
            print "last record saved:", records_to_save[-1]
            print "last timestamp saved:", records_to_save[-1]["base_timestamp"]
            records_to_save = []

        oai_record = safe_get_next_record(oai_records)

    # make sure to get the last ones
    if records_to_save:
        save_records_in_es(es, records_to_save, 1, chunk_size)
        print "last record saved:", records_to_save[-1]



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")


    # just for updating lots
    # function = s3_to_elastic
    # parser.add_argument('--url', nargs="?", type=str, help="elasticsearch connect url (example: --url http://70f78ABCD.us-west-2.aws.found.io:9200")
    # parser.add_argument('--first', nargs="?", type=str, help="first filename to process (example: --first ListRecords.14461")
    # parser.add_argument('--last', nargs="?", type=str, help="last filename to process (example: --last ListRecords.14461)")
    # parser.add_argument('--randomize', dest='randomize', action='store_true', help="pull random files from AWS")

    function = oaipmh_to_elastic
    parser.add_argument('--start_date', type=str, help="first date to pull stuff from oai-pmh (example: --start_date 2016-11-10")
    parser.add_argument('--end_date', type=str, help="last date to pull stuff from oai-pmh (example: --end_date 2016-11-10")

    # good for both of them
    parser.add_argument('--url', nargs="?", type=str, help="elasticsearch connect url (example: --url http://70f78ABCD.us-west-2.aws.found.io:9200")
    parser.add_argument('--threads', nargs="?", type=int, help="how many threads if multi")
    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

