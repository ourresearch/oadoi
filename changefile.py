import boto
import os

DATA_FEED_BUCKET_NAME = "unpaywall-data-feed"

def valid_changefile_api_keys():
    api_keys_string = os.getenv("VALID_UNPAYWALL_API_KEYS")
    return api_keys_string.split(",")

def get_file_from_bucket(filename):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(DATA_FEED_BUCKET_NAME)
    key = bucket.lookup(filename)
    return key

def get_changefile_dicts():
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(DATA_FEED_BUCKET_NAME)
    bucket_contents = bucket.list()
    response = []
    for bucket_file in bucket_contents:
        my_dict = {
            "filename": bucket_file.key,
            "size": bucket_file.size,
            "filetype": bucket_file.key.split(".", 1)[1],
            "last_modified": bucket_file.last_modified,
            "lines": bucket_file.size / 4200
        }
        response.append(my_dict)
    response.sort(key=lambda x:x['filename'], reverse=True)
    return response