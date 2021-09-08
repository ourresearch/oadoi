import datetime
import gzip
import hashlib
import random
import uuid

import boto3
import shortuuid

from app import db, logger
from page import PageBase


class UnmatchedRepoPage(PageBase):
    fulltext_type = db.Column(db.Text)

    def __init__(self, endpoint_id, pmh_id, url, **kwargs):
        if not (endpoint_id and pmh_id and url):
            raise ValueError('endpoint_id, pmh_id, url must be non-null')

        # old internal pmh_ids weren't prefixed with the endpoint_id
        # normalize to that format. endpoint_id and pmh_id are still unique together
        pmh_internal_id = pmh_id.removeprefix(f'{endpoint_id}:')

        # generate the same id for a given endpoint, pmh_id, and url
        id_seed = f'{endpoint_id}:{pmh_internal_id}:{url}'
        self.id = shortuuid.encode(
            uuid.UUID(bytes=hashlib.sha256(id_seed.encode('utf-8')).digest()[0:16])
        )

        self.endpoint_id = endpoint_id
        self.pmh_id = pmh_id
        self.url = url

        self.error = ""
        self.rand = random.random()
        self.updated = datetime.datetime.utcnow().isoformat()
        super(PageBase, self).__init__(**kwargs)

    def store_fulltext(self, fulltext_bytes, fulltext_type):
        bucket = 'unpaywall-tier-2-fulltext'

        self.fulltext_type = fulltext_type

        if fulltext_type and fulltext_bytes:
            try:
                logger.info(f'saving {len(fulltext_bytes)} {fulltext_type} bytes to s3://{bucket}/{self.id}')
                client = boto3.client('s3')
                client.put_object(Body=gzip.compress(fulltext_bytes), Bucket=bucket, Key=self.id)
            except Exception as e:
                logger.error(f'failed to save fulltext bytes: {e}')
                self.fulltext_type = None

    def store_landing_page(self, landing_page_markup):
        bucket = 'unpaywall-worksdb-repo-landing-page'
        key = f'{self.id}.gz'

        if landing_page_markup:
            try:
                logger.info(f'saving {len(landing_page_markup)} characters to s3://{bucket}/{key}')
                client = boto3.client('s3')
                client.put_object(Body=gzip.compress(landing_page_markup.encode('utf-8')), Bucket=bucket, Key=key)
            except Exception as e:
                logger.error(f'failed to save landing page text: {e}')

    def __repr__(self):
        return "<UnmatchedRepoPage ( {} ) {}, {}, {}>".format(self.id, self.endpoint_id, self.pmh_id, self.url)

