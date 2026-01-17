import json

import boto
from botocore.exceptions import ClientError
import boto3
from sqlalchemy import sql

from app import db, logger
from wunpaywall import DataFeedApiKey

WEEKLY_FEED = {
    'name': 'unpaywall-data-feed',
    'bucket': 'unpaywall-data-feed',
    'changefile-endpoint': 'feed/changefile',
    'interval': 'week',
    'file_dates': lambda filename: {
        'from_date': filename.split("_")[0].split("T")[0],
        'to_date': filename.split("_")[2].split("T")[0]
    },
}

DAILY_FEED = {
    'name': 'unpaywall-daily-data-feed',
    'bucket': 'unpaywall-daily-data-feed',
    'changefile-endpoint': 'daily-feed/changefile',
    'interval': 'day',
    'file_dates': lambda filename: {
        'date': filename.split("T")[0]
    },
}


def valid_changefile_api_keys():
    """Return valid API keys from RDS (unpaywall.data_feed_api_keys)."""
    return DataFeedApiKey.get_valid_api_keys()


def get_file_from_bucket(filename, feed=WEEKLY_FEED):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(feed['bucket'])
    key = bucket.lookup(filename)
    return key


def get_wunpaywall_file_from_bucket(filename, mode="daily"):
    bucket_name = "unpaywall-data-feed-walden"
    file_path = f"{mode}/{filename}"

    s3 = boto3.client('s3')

    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_path)
        return response
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey' or error_code == 'NoSuchBucket':
            logger.warning(f"File {filename} not found in {bucket_name}/{mode}")
        else:
            logger.error(f"Error accessing {filename} in {bucket_name}/{mode}: {str(e)}")
        return None


def get_changefile_dicts(api_key, feed=WEEKLY_FEED):
    response_dict = db.engine.execute(
        sql.text(u'select changefile_dicts from changefile_dicts where feed = :feed').bindparams(feed=feed['name'])
    ).fetchone()[0]

    return json.loads(response_dict.replace('__DATA_FEED_API_KEY__', json.dumps(api_key)[1:-1]))


def generate_presigned_download_url(filename, mode="daily", expiration=3600):
    """Generate a presigned URL for downloading a file from S3"""
    bucket_name = "unpaywall-data-feed-walden"
    file_path = f"{mode}/{filename}"

    s3_client = boto3.client('s3')

    try:
        # Check if file exists
        s3_client.head_object(Bucket=bucket_name, Key=file_path)

        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': file_path},
            ExpiresIn=expiration
        )

        return presigned_url

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey' or error_code == 'NoSuchBucket':
            return None
        else:
            raise e
