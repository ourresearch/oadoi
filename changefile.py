import boto
import os

DATA_FEED_BUCKET_NAME = "unpaywall-data-feed"

def valid_changefile_api_keys():
    api_keys_string = os.getenv("VALID_UNPAYWALL_API_KEYS")
    return api_keys_string.split(",")

def get_file_from_bucket(filename, api_key):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(DATA_FEED_BUCKET_NAME)
    key = bucket.lookup(filename)
    return key

def get_changefile_dicts(api_key):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(DATA_FEED_BUCKET_NAME)
    bucket_contents_all = bucket.list()
    bucket_contents = []
    for bucket_file in bucket_contents_all:
        filename = bucket_file.key
        if ("changed_dois_with_versions" in filename) \
            and (filename.endswith(".csv.gz") or filename.endswith(".jsonl.gz")):
            my_key = bucket.get_key(bucket_file.name)
            if my_key.metadata.get("updated", None) is not None:
                bucket_contents.append(my_key)

    response = []
    for bucket_file in bucket_contents:
        simple_key = bucket_file.key
        simple_key = simple_key.replace("changed_dois_with_versions_", "")
        simple_key = simple_key.split(".")[0]
        from_date = simple_key.split("_")[0]
        to_date = simple_key.split("_")[2]
        my_dict = {
            "filename": bucket_file.key,
            "size": bucket_file.size,
            "filetype": bucket_file.name.split(".")[1],
            "url": "http://api.unpaywall.org/feed/changefile/{}?api_key={}".format(bucket_file.name, api_key),
            "last_modified": bucket_file.metadata.get("updated", None),
            "lines": int(bucket_file.metadata.get("lines", 0)),
            "from_date": from_date.split("T")[0],
            "to_date": to_date.split("T")[0]
        }
        response.append(my_dict)
    response.sort(key=lambda x:x['filename'], reverse=True)
    return response