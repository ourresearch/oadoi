from enum import Enum
from urllib.parse import quote

import boto3
import botocore

from const import PDF_ARCHIVE_BUCKET, GROBID_XML_BUCKET


class PDFVersion(Enum):
    PUBLISHED = 'published'
    ACCEPTED = 'accepted'
    SUBMITTED = 'submitted'

    def s3_key(self, doi):
        return f"{self.s3_prefix}{quote(doi, safe='')}.pdf"

    def grobid_s3_key(self, doi):
        return f'{self.s3_prefix}{quote(doi, safe="")}.xml'

    @property
    def s3_prefix(self):
        if not self == PDFVersion.PUBLISHED:
            return f'{self.value}_'
        return ''

    def s3_url(self, doi):
        return f's3://{PDF_ARCHIVE_BUCKET}/{self.s3_key(doi)}'

    @classmethod
    def from_version_str(cls, version_str: str):
        for version in cls:
            if version.value in version_str.lower():
                return version
        return None

    def in_s3(self, doi) -> bool:
        try:
            self.s3.get_object(Bucket=PDF_ARCHIVE_BUCKET, Key=self.s3_key(doi))
            return True
        except botocore.exceptions.ClientError as e:
            return False

    def grobid_in_s3(self, doi):
        try:
            self.s3.get_object(Bucket=GROBID_XML_BUCKET,
                               Key=self.grobid_s3_key(doi))
            return True
        except botocore.exceptions.ClientError as e:
            return False


PDFVersion.s3 = boto3.client('s3', verify=False)
