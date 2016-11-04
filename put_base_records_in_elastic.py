import boto
import os
from time import sleep
from time import time
from util import elapsed
import zlib
import re
import json
import argparse
from elasticsearch import Elasticsearch, RequestsHttpConnection, serializer, compat, exceptions
from elasticsearch.helpers import parallel_bulk

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
            print u"Record is missing required key '{}'!".format(k)
            # print record
            return False

    if record["oa"] == 0:
        print u"record {} is closed access. skipping.".format(record["id"])
        return False

    return True




def main(first=None, last=None):
    print "running main()"

    # set up elasticsearch
    INDEX_NAME = "base"
    TYPE_NAME = "record"
    es = Elasticsearch(os.getenv("ELASTICSEARCH_URL"),
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

    # set up aws s3 connection
    conn = boto.connect_s3(
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    my_bucket = conn.get_bucket('base-initial')

    i = 0
    records_to_save = []

    for key in my_bucket.list():
        if not key.name.startswith("base_dc_dump") or not key.name.endswith(".gz"):
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


            if is_complete(record):
                my_record = {
                    '_op_type': 'index',
                    '_index': INDEX_NAME,
                    '_type': 'record',
                    '_id': record["id"],
                    'doc': record
                }
                records_to_save.append(my_record)
        i += 1

        if len(records_to_save) >= 10000:
            # have to do it this way, because is parallel_bulk is a generator so you have to call it to
            # have it do the work.  see https://discuss.elastic.co/t/helpers-parallel-bulk-in-python-not-working/39498
            print u"saving a chunk of {} records.".format(len(records_to_save))
            start_time = time()
            for success, info in parallel_bulk(es, actions=records_to_save, refresh=False, request_timeout=60, thread_count=4, chunk_size=500):
                if not success:
                    print('A document failed:', info)

            # res = es.bulk(index=INDEX_NAME, body=records_to_save, refresh=False, request_timeout=60)
            print u"done sending them to elastic in {}s".format(elapsed(start_time, 4))
            records_to_save = []


    # make sure to get the last ones
    res = es.bulk(index=INDEX_NAME, body=records_to_save, refresh=False, request_timeout=60)
    print u"done."




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    # just for updating lots
    parser.add_argument('--first', nargs="?", type=str, help="start filename")
    parser.add_argument('--last', nargs="?", type=str, help="end filename")
    parsed = parser.parse_args()

    main(parsed.first, parsed.last)