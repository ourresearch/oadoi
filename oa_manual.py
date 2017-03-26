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

    # otherwise links to figshare match that only has data, not the article
    override_dict["10.1126/science.aaf3777"]["free_pdf_url"] = None
    override_dict["10.1126/science.aaf3777"]["free_metadata_url"] = None

    #otherwise links to a metadata page that doesn't have the PDF because have to request a copy: https://openresearch-repository.anu.edu.au/handle/1885/103608
    override_dict["10.1126/science.aad2622"]["free_pdf_url"] = "https://lra.le.ac.uk/bitstream/2381/38048/6/Waters%20et%20al%20draft_post%20review_v2_clean%20copy.pdf"

    # otherwise led to http://www.researchonline.mq.edu.au/vital/access/services/Download/mq:39727/DS01 and authorization error
    override_dict["10.1111/j.1461-0248.2008.01185.x"]["free_pdf_url"] = None

    # override old-style webpage
    override_dict["10.1210/jc.2016-2141"]["free_pdf_url"] = "https://oup.silverchair-cdn.com/oup/backfile/Content_public/Journal/jcem/101/12/10.1210_jc.2016-2141/2/jcem4779.pdf?Expires=1490835793&Signature=KQrES-S5gUH7G4qhkcXTs4AtqDIudaen9T0guvd2ZEnSqqhqAVCMMQiR3xkl4PBLPccAbJ8X5Yb6p-wTyYl29BtZBeUoXwx7KC~MTjDLBnawgW5xyOYLbNkbgM0auUOMlQbEwHdO6ekJiS97Y1x1pDdiyevDKMWWMxOmMAj5Y447AAE0bkN2PDpMTPv2TbawhQJNwR0hL2gMAPjW1TdF2qYrs~7Jo6uZWKpsuizP4e4bqjwiu0PJT3rsWbAIfm7c7RLPbByZKVToE3-CPQncnrQJ8HHOHd73YH7A3h9lpiXorVcWsY5xPZYCe1ELIGvzzgtIUMaKfRa0V0ZFj-t2VQ__&Key-Pair-Id=APKAIUCZBIA4LVPAVW3Q"

    return override_dict
