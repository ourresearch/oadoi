import boto
import os
from StringIO import StringIO
from time import sleep
import zlib
from lxml import etree
import re

class MissingTagException(Exception):
    pass


def tag_match(tagname, str, allow_none=False, concat=False):
    regex_str = "<{}>(.+?)</{}>".format(tagname, tagname)
    matches = re.findall(regex_str, str)

    if len(matches) == 0:
        if allow_none:
            return None
        else:
            print "something broke in this record:"
            print str
            raise MissingTagException

    if concat:
        return "|".join(matches)
    else:
        return matches[0]


def main():
    print "running main()"
    conn = boto.connect_s3(
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    my_bucket = conn.get_bucket('base-initial')

    i = 0
    for key in my_bucket.list():
        if not key.name.startswith("base_dc_dump") or not key.name.endswith(".gz"):
            continue

        if i >= 2:
            break

        print "getting this key...", key.name



        print "done."

        # that second arg is important. see http://stackoverflow.com/a/18319515
        res = zlib.decompress(key.get_contents_as_string(), 16+zlib.MAX_WBITS)


        obj = {}
        records = re.findall("<record>.+?</record>", res, re.DOTALL)
        for record in records:

            obj["id"] = tag_match("identifier", record)
            obj["title"] = tag_match("dc:title", record)
            obj["oa"] = tag_match("base_dc:oa", record)
            obj["license"] = tag_match("base_dc:rights", record, allow_none=True)

            obj["creators"] = tag_match("dc:creator", record, concat=True)
            obj["identifiers"] = tag_match("dc:identifier", record, concat=True)

            obj["relations"] = tag_match("dc:relation", record, concat=True, allow_none=True)
            obj["hosts"] = tag_match("base_dc:collname", record, concat=True, allow_none=True)





            print obj







        i += 1






if __name__ == "__main__":
    main()