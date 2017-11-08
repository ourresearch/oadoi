from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from cStringIO import StringIO

from app import logger



def convert_pdf_to_txt(r):
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)

    if r.status_code != 200:
        logger.info(u"error: status code {} in convert_pdf_to_txt".format(r.status_code))
        return None

    fp = StringIO(r.content)

    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 3
    caching = True
    pagenos=set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password, caching=caching, check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    device.close()
    retstr.close()
    # logger.info(text)
    return text
