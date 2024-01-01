from enum import Enum
from urllib.parse import quote

import botocore
from sqlalchemy import text

from app import s3_conn, logger, db

from const import PDF_ARCHIVE_BUCKET, GROBID_XML_BUCKET
from s3_util import check_exists, get_object


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
        return check_exists(PDF_ARCHIVE_BUCKET, self.s3_key(doi))

    def grobid_in_s3(self, doi):
        return check_exists(GROBID_XML_BUCKET, self.grobid_s3_key(doi))

    def get_grobid_xml_obj(self, doi):
        return get_object(GROBID_XML_BUCKET, self.grobid_s3_key(doi))

    def get_pdf_obj(self, doi):
        return get_object(PDF_ARCHIVE_BUCKET, self.s3_key(doi))


def save_pdf(doi, content, version=PDFVersion.PUBLISHED):
    if not content:
        return False
    logger.info(
        f'saving {len(content)} characters to {version.s3_url(doi)}')
    try:
        s3_conn.put_object(
            Body=content,
            Bucket=PDF_ARCHIVE_BUCKET,
            Key=version.s3_key(doi)
        )
        return True
    except Exception as e:
        logger.error(f'failed to save pdf: {e}')
        return False


def enqueue_pdf_parsing(doi, version: PDFVersion = PDFVersion.PUBLISHED,
                        commit=True):
    db.session.execute(text(
        "INSERT INTO recordthresher.pdf_update_ingest (doi, pdf_version) VALUES (:doi, :version) ON CONFLICT(doi) DO UPDATE SET finished = NULL;").bindparams(
        doi=doi, version=version.value))
    if commit:
        db.session.commit()


def is_pdf(contents: bytes) -> bool:
    return contents.startswith(b"%PDF-")
