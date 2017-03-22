from collections import defaultdict

from time import time
from util import elapsed

# things to set here:
#       license, free_metadata_url, free_pdf_url
# free_fulltext_url is set automatically from free_metadata_url and free_pdf_url

def get_overrides_dict():
    override_dict = defaultdict(dict)

    # cindy wu example
    override_dict["10.1038/nature21360"]["free_pdf_url"] = "https://arxiv.org/pdf/1703.01424.pdf"

    # example from twitter
    override_dict["10.1021/acs.jproteome.5b00852"]["free_pdf_url"] = "http://pubs.acs.org/doi/pdfplus/10.1021/acs.jproteome.5b00852"

    # have the unpaywall example go straight to the PDF, not the metadata page
    override_dict["10.1098/rspa.1998.0160"]["free_pdf_url"] = "https://arxiv.org/pdf/quant-ph/9706064.pdf"

    # missed, not in BASE, from Maha Bali in email
    override_dict["10.1080/13562517.2014.867620"]["free_pdf_url"] = "http://dar.aucegypt.edu/bitstream/handle/10526/4363/Final%20Maha%20Bali%20TiHE-PoD-Empowering_Sept30-13.pdf"

    return override_dict
