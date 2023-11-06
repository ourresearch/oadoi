import boto3
import botocore

_s3 = boto3.client('s3')


def make_s3():
    return boto3.client('s3')


def _get_obj(bucket, key, f, s3=None, _raise=False):
    if not s3:
        s3 = _s3
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return f(obj)
    except botocore.exceptions.ClientError as e:
        if not _raise:
            return f(None)
        raise e


def check_exists(bucket, key, s3=None, _raise=False):
    return _get_obj(bucket, key, lambda obj: bool(obj), s3=s3, _raise=_raise)


def get_object(bucket, key, s3=None, _raise=False):
    return _get_obj(bucket, key, lambda obj: obj, s3=s3, _raise=_raise)


def upload_obj(bucket, key, body, s3=None):
    if not s3:
        s3 = _s3
    s3.upload_fileobj(body, bucket, key)
