import itertools
import pdftotext
from cStringIO import StringIO

from app import logger


def convert_pdf_to_txt(r, max_pages=3):
    return '\n'.join(convert_pdf_to_txt_pages(r, max_pages))


def convert_pdf_to_txt_pages(r, max_pages=3):
    if r.status_code != 200:
        logger.info(u"error: status code {} in convert_pdf_to_txt".format(r.status_code))
        return None

    if not r.encoding:
        r.encoding = "utf-8"
    fp = StringIO(r.content_big())

    return list(itertools.islice(pdftotext.PDF(fp), max_pages))
