import boto


def get_daily_snapshot_key():
    s3 = boto.connect_s3()
    bucket = s3.get_bucket('unpaywall-daily-snapshots')
    bucket_contents_all = bucket.list()

    objects = sorted(bucket_contents_all, key=lambda o: o.key)

    if not objects:
        return None

    return bucket.get_key(objects[-1].name)
