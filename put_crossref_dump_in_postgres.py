import os
from boto.s3.connection import S3Connection
import datetime
import json
import argparse
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from util import JSONSerializerPython2
from util import elapsed
from util import clean_doi
from util import safe_commit

# set up elasticsearch
INDEX_NAME = "crossref"
TYPE_NAME = "crosserf_api"  #TYPO!!!  but i think for now we run with it???

# from http://stackoverflow.com/a/16890018/596939
def getS3ResultsAsIterator(key, prefix):
    s3_conn = S3Connection(os.getenv("AWS_ACCESS_KEY_ID"), os.getenv("AWS_SECRET_ACCESS_KEY"))
    bucket_obj = s3_conn.get_bucket(key)
    # go through the list of files in the key
    for f in bucket_obj.list(prefix=prefix):
        unfinished_line = ''
        for byte in f:
            byte = unfinished_line + byte
            #split on whatever, or use a regex with re.split()
            lines = byte.split('\n')
            unfinished_line = lines.pop()
            for line in lines:
                yield line

def s3_to_postgres(chunk_size=None):
    key_name = "crossref-es"
    prefix = "initial"

    num_objects_to_save = 0
    for line in getS3ResultsAsIterator(key_name, prefix):
        data = json.loads(line)
        num_objects_to_save += 1
        crossref_meta = CrossrefMeta(data["_source"])
        print "crossref_meta", crossref_meta
        db.session.merge(crossref_meta)

        if num_objects_to_save >= chunk_size:
            print "committing"
            safe_commit(db)
            num_objects_to_save = 0

    safe_commit(db)


class CrossrefMeta(db.Model):
    doi = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    year = db.Column(db.Text)
    content = db.Column(JSONB)

    def __init__(self, content):
        dirty_doi = content["doi"]
        if not clean_doi(dirty_doi):
            return

        self.doi = clean_doi(dirty_doi)
        if "year" in content:
            self.year = content["year"]
        self.updated = datetime.datetime.utcnow()
        del content["doi"]
        self.content = content

    def to_dict(self):
        return self.content

    def __repr__(self):
        return u"<CrossrefMeta ({})>".format(
            self.doi
        )

# db.create_all()
# commit_success = safe_commit(db)
# if not commit_success:
#     print u"COMMIT fail making objects"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    function = s3_to_postgres
    print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    function(**vars(parsed))

