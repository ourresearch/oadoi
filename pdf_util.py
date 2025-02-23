import time
import uuid
from datetime import datetime
from enum import Enum
from urllib.parse import quote

from sqlalchemy import text

from app import s3_conn, logger, db

from const import PDF_ARCHIVE_BUCKET, GROBID_XML_BUCKET, PDF_ARCHIVE_BUCKET_NEW
from s3_util import check_exists, get_object, harvest_pdf_table, s3


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
        if not version_str:
            return None
        for version in cls:
            if version.value in version_str.lower():
                return version
        return None

    def valid_in_s3(self, doi) -> bool:
        return check_valid_pdf(PDF_ARCHIVE_BUCKET, self.s3_key(doi))

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


def save_pdf_new(content, native_id, native_id_ns, version=PDFVersion.PUBLISHED, url='', resolved_url=''):
    if not content:
        return
    new_key = str(uuid.uuid4()) + '.pdf'
    encoded_url = quote(str(url or ''))
    encoded_resolved_url = quote(str(resolved_url or ''))
    s3.put_object(
        Bucket=PDF_ARCHIVE_BUCKET_NEW,
        Key=new_key,
        Body=content,
        Metadata={
            'url': encoded_url,
            'resolved_url': encoded_resolved_url,
            'created_date': datetime.utcnow().isoformat(),
            'created_timestamp': str(int(time.time())),
            'id': new_key.replace('.pdf', ''),
            'native_id': native_id.lower().strip(),
            'native_id_namespace': native_id_ns
        })
    item = {
        'id': new_key.replace('.pdf', ''),
        'native_id': native_id.lower().strip(),
        'native_id_namespace': native_id_ns,
        'url': url,
        'type': version.value,
        's3_key': new_key,
        's3_path': f's3://{PDF_ARCHIVE_BUCKET_NEW}/{new_key}',
        'created_timestamp': int(time.time()),
        'created_date': datetime.utcnow().isoformat()
    }
    if native_id_ns == 'doi':
        item['normalized_doi'] = native_id
    harvest_pdf_table.put_item(Item=item)


def enqueue_pdf_parsing(doi, version: PDFVersion = PDFVersion.PUBLISHED,
                        commit=True):
    stmnt = text(
        "INSERT INTO recordthresher.pdf_update_ingest (doi, pdf_version) VALUES (:doi, :version) ON CONFLICT(doi, pdf_version) DO UPDATE SET finished = NULL;").bindparams(
        doi=doi, version=version.value)
    db.session.execute(stmnt)
    if commit:
        db.session.commit()


def check_valid_pdf(bucket, key, s3=None, _raise=False):
    obj = get_object(bucket, key, s3=s3, _raise=_raise)
    if not obj:
        return False
    contents = obj['Body'].read()
    if contents is not None:
        return is_pdf(contents)
    return False


def is_pdf(contents: bytes) -> bool:
    return contents.startswith(b"%PDF-")
