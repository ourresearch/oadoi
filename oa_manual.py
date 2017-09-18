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
    override_dict["10.1038/nature21360"]["oa_color"] = "green"

    # example from twitter
    override_dict["10.1021/acs.jproteome.5b00852"]["free_pdf_url"] = "http://pubs.acs.org/doi/pdfplus/10.1021/acs.jproteome.5b00852"
    override_dict["10.1021/acs.jproteome.5b00852"]["oa_color"] = "gold"

    # have the unpaywall example go straight to the PDF, not the metadata page
    override_dict["10.1098/rspa.1998.0160"]["free_pdf_url"] = "https://arxiv.org/pdf/quant-ph/9706064.pdf"
    override_dict["10.1098/rspa.1998.0160"]["oa_color"] = "green"

    # missed, not in BASE, from Maha Bali in email
    override_dict["10.1080/13562517.2014.867620"]["free_pdf_url"] = "http://dar.aucegypt.edu/bitstream/handle/10526/4363/Final%20Maha%20Bali%20TiHE-PoD-Empowering_Sept30-13.pdf"
    override_dict["10.1080/13562517.2014.867620"]["oa_color"] = "green"

    # otherwise links to figshare match that only has data, not the article
    override_dict["10.1126/science.aaf3777"]["free_pdf_url"] = None
    override_dict["10.1126/science.aaf3777"]["free_metadata_url"] = None
    override_dict["10.1126/science.aaf3777"]["oa_color"] = None

    #otherwise links to a metadata page that doesn't have the PDF because have to request a copy: https://openresearch-repository.anu.edu.au/handle/1885/103608
    override_dict["10.1126/science.aad2622"]["free_pdf_url"] = "https://lra.le.ac.uk/bitstream/2381/38048/6/Waters%20et%20al%20draft_post%20review_v2_clean%20copy.pdf"
    override_dict["10.1126/science.aad2622"]["oa_color"] = "green"

    # otherwise led to http://www.researchonline.mq.edu.au/vital/access/services/Download/mq:39727/DS01 and authorization error
    override_dict["10.1126/science.aad2622"]["free_pdf_url"] = None
    override_dict["10.1126/science.aad2622"]["oa_color"] = None

    # otherwise led to https://dea.lib.unideb.hu/dea/bitstream/handle/2437/200488/file_up_KMBT36220140226131332.pdf;jsessionid=FDA9F1A60ACA567330A8B945208E3CA4?sequence=1
    override_dict["10.1007/978-3-211-77280-5"]["free_pdf_url"] = None
    override_dict["10.1007/978-3-211-77280-5"]["oa_color"] = None

    # override old-style webpage
    override_dict["10.1210/jc.2016-2141"]["free_pdf_url"] = "https://academic.oup.com/jcem/article-lookup/doi/10.1210/jc.2016-2141"
    override_dict["10.1210/jc.2016-2141"]["oa_color"] = "gold"

    # not indexing this location yet, from @rickypo
    override_dict["10.1207/s15327957pspr0203_4"]["free_pdf_url"] = "http://www2.psych.ubc.ca/~schaller/528Readings/Kerr1998.pdf"
    # also, work around broken url extraction from sage
    override_dict["10.1210/jc.2016-2141"]["free_pdf_url"] = "http://www2.psych.ubc.ca/~schaller/528Readings/Kerr1998.pdf"
    override_dict["10.1210/jc.2016-2141"]["oa_color"] = "green"

    # mentioned in world bank as good unpaywall example
    override_dict["10.3386/w23298"]["free_pdf_url"] = "https://economics.mit.edu/files/12774"
    override_dict["10.3386/w23298"]["oa_color"] = "green"

    # from email
    override_dict["10.1038/nature21377"]["free_pdf_url"] = "http://eprints.whiterose.ac.uk/112179/1/ppnature21377_Dodd_for%20Symplectic.pdf"
    override_dict["10.1038/nature21377"]["oa_color"] = "green"

    return override_dict
