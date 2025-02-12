import logging
from gzip import decompress
from urllib.parse import quote

import boto3
import botocore

from const import LANDING_PAGE_ARCHIVE_BUCKET
from util import normalize_doi

s3 = boto3.client('s3')

harvest_html_table = boto3.resource('dynamodb',
        region_name='us-east-1',
    ).Table('harvested-html')

harvest_pdf_table = boto3.resource('dynamodb',
        region_name='us-east-1',
    ).Table('harvested-pdf')

def mute_boto_logging():
    libs_to_mum = [
        'boto',
        'boto3',
        'botocore',
        's3transfer'
    ]
    for lib in libs_to_mum:
        logging.getLogger(lib).setLevel(logging.CRITICAL)


def make_s3():
    return boto3.client('s3')


def _get_obj(bucket, key, f, s3=None, _raise=False):
    if not s3:
        s3 = s3
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
        s3 = s3
    s3.upload_fileobj(body, bucket, key)


def landing_page_key(doi: str):
    doi = normalize_doi(doi)
    return quote(doi.lower(), safe='')


def get_landing_page(doi):
    obj = get_object(LANDING_PAGE_ARCHIVE_BUCKET, landing_page_key(doi))
    contents = obj['Body'].read()
    return decompress(contents)
