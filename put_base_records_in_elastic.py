import boto
import os
from time import sleep
from util import elapsed
import zlib
import re
from elasticsearch import Elasticsearch

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
            print record
            return False

    if record["oa"] == 0:
        print u"record {} is closed access. skipping.".format(record["id"])
        return False

    return True




def main():
    print "running main()"

    # set up elasticsearch
    INDEX_NAME = "base"
    TYPE_NAME = "record"
    es = Elasticsearch(os.getenv("ELASTICSEARCH_URL"))
    if es.indices.exists(INDEX_NAME):
        print("deleting '%s' index..." % (INDEX_NAME))
        res = es.indices.delete(index = INDEX_NAME)
        print(" response: '%s'" % (res))

    print u"creating index"
    res = es.indices.create(index=INDEX_NAME)

    # set up aws s3 connection
    conn = boto.connect_s3(
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    my_bucket = conn.get_bucket('base-initial')

    i = 0
    for key in my_bucket.list():
        if not key.name.startswith("base_dc_dump") or not key.name.endswith(".gz"):
            continue

        # if i >= 2:
        #     break

        print "getting this key...", key.name
        print "done."

        # that second arg is important. see http://stackoverflow.com/a/18319515
        res = zlib.decompress(key.get_contents_as_string(), 16+zlib.MAX_WBITS)

        xml_records = re.findall("<record>.+?</record>", res, re.DOTALL)

        records_to_save = []
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
                op_dict = {
                    "index": {
                        "_index": INDEX_NAME,
                        "_type": TYPE_NAME,
                        "_id": record["id"]
                    }
                }
                records_to_save.append(op_dict)
                records_to_save.append(record)



        i += 1

        # save it!
        print u"saving a chunk of {} records.".format(len(records_to_save))

        print u"now sending them to elastic!!!"
        # print "\n\n", records_to_save, "\n\n"
        res = es.bulk(index=INDEX_NAME, body=records_to_save, refresh=True)
        print u"done sending them to elastic!!!"




if __name__ == "__main__":
    main()