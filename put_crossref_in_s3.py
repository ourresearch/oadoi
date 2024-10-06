import argparse
import datetime
import json
import os
import pytz
import time

import boto3
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app import logging

CROSSREF_API_KEY = os.getenv('CROSSREF_API_KEY')


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10),
       retry=retry_if_exception_type(requests.exceptions.RequestException))
def make_request_with_retry(url, headers):
    response = requests.get(url, headers=headers)

    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        logging.warning(f"Rate limit exceeded (429). Retrying after {retry_after} seconds.")
        time.sleep(retry_after)
        response.raise_for_status()

    elif response.status_code >= 500:
        logging.error(f"Server error {response.status_code} for URL {url}. Retrying...")
        response.raise_for_status()

    return response


def get_crossref_data(filter_params, s3_bucket, s3_prefix):
    base_url = 'https://api.crossref.org/works'
    headers = {
        "Accept": "application/json",
        "User-Agent": "mailto:dev@ourresearch.org",
        "crossref-api-key": CROSSREF_API_KEY
    }
    per_page = 500
    cursor = '*'
    page_number = 1
    has_more_pages = True

    url_template = f"{base_url}?filter={{filter}}&rows={{rows}}&cursor={{cursor}}"

    while has_more_pages:
        url = url_template.format(
            filter=filter_params,
            rows=per_page,
            cursor=cursor
        )

        response = make_request_with_retry(url, headers)

        logging.info(f"Requesting page {page_number} from URL {url}.")

        data = response.json()
        items = data['message']['items']

        if items:
            s3_key = f'{s3_prefix}/works_page_{page_number}.json'
            save_to_s3(items, s3_bucket, s3_key)
        else:
            logging.info(f"No more items to fetch on page {page_number}. Ending pagination.")
            has_more_pages = False

        if 'next-cursor' not in data['message']:
            logging.info("No next cursor found, pagination complete.")
            has_more_pages = False

        cursor = data['message']['next-cursor']
        page_number += 1

        time.sleep(.5)


def save_to_s3(json_data, s3_bucket, s3_key):
    logging.info(f"Saving crossref works to S3 bucket {s3_bucket} with key {s3_key}.")
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket=s3_bucket,
        Key=s3_key,
        Body=json.dumps(json_data),
        ContentType='application/json'
    )


def main():
    parser = argparse.ArgumentParser(description='Pull Crossref data (new works or updates).')
    parser.add_argument('mode', choices=['new', 'updates'], help='Specify whether to pull new works or updates.')
    args = parser.parse_args()

    s3_bucket = 'openalex-elt'
    now = datetime.datetime.now(pytz.utc)
    today_str = now.strftime('%Y-%m-%d')
    yesterday = now - datetime.timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')

    if args.mode == 'new':
        filter_params = f'from-created-date:{today_str},until-created-date:{today_str}'
        s3_prefix = f'crossref/new-works/{now.strftime("%Y/%m/%d/%H")}'
        get_crossref_data(filter_params, s3_bucket, s3_prefix)

    elif args.mode == 'updates':
        filter_params = f'from-index-date:{yesterday_str},until-index-date:{yesterday_str}'
        s3_prefix = f'crossref/updates/{yesterday.strftime("%Y/%m/%d")}'
        get_crossref_data(filter_params, s3_bucket, s3_prefix)


if __name__ == '__main__':
    main()
