import datetime
import gzip
import random

import boto3
import shortuuid

from app import db
from page import PageBase


class UnmatchedRepoPage(PageBase):
    fulltext_type = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()
        self.error = ""
        self.rand = random.random()
        self.updated = datetime.datetime.utcnow().isoformat()
        super(PageBase, self).__init__(**kwargs)

    @staticmethod
    def from_page_new(page_new):
        unmatched_page = UnmatchedRepoPage.query.filter(
            UnmatchedRepoPage.pmh_id == page_new.pmh_id,
            UnmatchedRepoPage.url == page_new.url
        ).scalar()

        if not unmatched_page:
            unmatched_page = UnmatchedRepoPage(pmh_id=page_new.pmh_id, url=page_new.url)
            unmatched_page.title = page_new.title
            unmatched_page.normalized_title = page_new.normalized_title
            unmatched_page.endpoint_id = page_new.endpoint_id

        return unmatched_page

    def store_fulltext(self, fulltext_bytes, fulltext_type):
        client = boto3.client('s3')
        client.put_object(Body=gzip.compress(fulltext_bytes), Bucket='unpaywall-tier-2-fulltext', Key='Hzb6iY8Yed9sh53c5rVHpE')
        self.fulltext_type = fulltext_type

