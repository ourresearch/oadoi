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



#
#
# def s3_to_postgres(chunk_size=None):
#     key_name = "crossref-es"
#     prefix = "initial"
#
#     total_saved_objects = 0
#     for line in getS3ResultsAsIterator(key_name, prefix):
#         data = json.loads(line)
#         total_saved_objects += 1
#         crossref_meta = CrossrefMeta(data["_source"])
#         db.session.merge(crossref_meta)
#
#         if (total_saved_objects % chunk_size) == 0:
#             print u"committing, offset: {}".format(total_saved_objects)
#             safe_commit(db)
#
#     safe_commit(db)
#
#
# class CrossrefMeta(db.Model):
#     doi = db.Column(db.Text, primary_key=True)
#     # updated = db.Column(db.DateTime)
#     # year = db.Column(db.Text)
#     # content = db.Column(JSONB)
#
#     def __init__(self, content):
#         dirty_doi = content["doi"]
#         if not clean_doi(dirty_doi):
#             return
#
#         self.doi = clean_doi(dirty_doi)
#
#         # self.updated = datetime.datetime.utcnow()
#         # if "year" in content:
#         #     self.year = content["year"]
#         # del content["doi"]
#         # self.content = content
#
#     # def to_dict(self):
#     #     return self.content
#
#     def __repr__(self):
#         return u"<CrossrefMeta ({})>".format(
#             self.doi
#         )



# db.create_all()
# commit_success = safe_commit(db)
# if not commit_success:
#     print u"COMMIT fail making objects"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff.")

    parser.add_argument('--chunk_size', nargs="?", type=int, default=100, help="how many docs to put in each POST request")

    parsed = parser.parse_args()

    # the python way in this file  was too slow
    # did it with unix and /copy instead.  notes follow.

    # log into aws
    # cat crossref_es_dump6.json | tr '"' '\n' | grep -oh "10\..*/.*" | grep -v "10.1002/tdm_license_1" > crossref_dois2.txt
    # psql postgres://ublgigpkjaiofe:p8ntnr429q0q0h1dss2ughggcrf@ec2-54-197-255-74.compute-1.amazonaws.com:5432/deseqi91vgcnci?ssl=true -c "\copy crossref_dois from 'crossref_dois.txt';"
    #
    # create table doi_result as
    # 	(select doi as id, null::timestamp as updated, null::JSONB as content
    # 		from crossref_dois group by doi)
    #
    # ALTER TABLE "public"."doi_result" ADD PRIMARY KEY ("id");

    # function = s3_to_postgres
    # print u"calling {} with these args: {}".format(function.__name__, vars(parsed))
    # function(**vars(parsed))

