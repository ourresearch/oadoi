from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from io import BytesIO
from app import logger
from cStringIO import StringIO



def convert_pdf_to_txt(r):
    text = None

    rsrcmgr = PDFResourceManager()
    retstr = BytesIO()
    codec = 'utf-8'
    laparams = LAParams()

    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)

    if r.status_code != 200:
        logger.info(u"error: status code {} in convert_pdf_to_txt".format(r.status_code))
        return None

    if not r.encoding:
        r.encoding = "utf-8"
    fp = StringIO(r.content_big())

    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 3
    caching = True
    pagenos = set()
    pages = PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password, caching=caching, check_extractable=True)

    for page in pages:
        interpreter.process_page(page)

    text = retstr.getvalue()

    device.close()
    retstr.close()
    # logger.info(text)
    return text
