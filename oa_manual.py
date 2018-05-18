from collections import defaultdict

from time import time
from util import elapsed

# things to set here:
#       license, free_metadata_url, free_pdf_url
# free_fulltext_url is set automatically from free_metadata_url and free_pdf_url

def get_overrides_dict():
    override_dict = defaultdict(dict)

    # cindy wu example
    override_dict["10.1038/nature21360"] = {
        "pdf_url": "https://arxiv.org/pdf/1703.01424.pdf",
        "version": "submittedVersion"
    }

    # example from twitter
    override_dict["10.1021/acs.jproteome.5b00852"] = {
        "pdf_url": "http://pubs.acs.org/doi/pdfplus/10.1021/acs.jproteome.5b00852",
        "host_type_set": "publisher",
        "version": "publishedVersion"
    }

    # have the unpaywall example go straight to the PDF, not the metadata page
    override_dict["10.1098/rspa.1998.0160"] = {
        "pdf_url": "https://arxiv.org/pdf/quant-ph/9706064.pdf",
        "version": "submittedVersion"
    }

    # missed, not in BASE, from Maha Bali in email
    override_dict["10.1080/13562517.2014.867620"] = {
        "pdf_url": "http://dar.aucegypt.edu/bitstream/handle/10526/4363/Final%20Maha%20Bali%20TiHE-PoD-Empowering_Sept30-13.pdf",
        "version": "submittedVersion"
    }

    # otherwise links to figshare match that only has data, not the article
    override_dict["110.1126/science.aaf3777"] = {}

    #otherwise links to a metadata page that doesn't have the PDF because have to request a copy: https://openresearch-repository.anu.edu.au/handle/1885/103608
    override_dict["10.1126/science.aad2622"] = {
        "pdf_url": "https://lra.le.ac.uk/bitstream/2381/38048/6/Waters%20et%20al%20draft_post%20review_v2_clean%20copy.pdf",
        "version": "submittedVersion"
    }

    # otherwise led to http://www.researchonline.mq.edu.au/vital/access/services/Download/mq:39727/DS01 and authorization error
    override_dict["10.1126/science.aad2622"] = {}

    # else goes here: http://www.it-c.dk/people/schmidt/papers/complexity.pdf
    override_dict["10.1007/978-1-84800-068-1_9"] = {}

    # otherwise led to https://dea.lib.unideb.hu/dea/bitstream/handle/2437/200488/file_up_KMBT36220140226131332.pdf;jsessionid=FDA9F1A60ACA567330A8B945208E3CA4?sequence=1
    override_dict["10.1007/978-3-211-77280-5"] = {}

    # otherwise led to publisher page but isn't open
    override_dict["10.1016/j.renene.2015.04.017"] = {}

    # override old-style webpage
    override_dict["10.1210/jc.2016-2141"] = {
        "pdf_url": "https://academic.oup.com/jcem/article-lookup/doi/10.1210/jc.2016-2141",
        "host_type_set": "publisher",
        "version": "publishedVersion",
    }

    # not indexing this location yet, from @rickypo
    override_dict["10.1207/s15327957pspr0203_4"] = {
        "pdf_url": "http://www2.psych.ubc.ca/~schaller/528Readings/Kerr1998.pdf",
        "version": "submittedVersion"
    }

    # mentioned in world bank as good unpaywall example
    override_dict["10.3386/w23298"] = {
        "pdf_url": "https://economics.mit.edu/files/12774",
        "version": "submittedVersion"
    }

    # from email, has bad citesserx cached version
    override_dict["10.1007/bf02693740"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.536.6939&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1038/nature21377"] = {
        "pdf_url": "http://eprints.whiterose.ac.uk/112179/1/ppnature21377_Dodd_for%20Symplectic.pdf",
        "version": "submittedVersion"
    }

    # from email
    override_dict["10.1016/j.gtc.2016.09.007"] = {
        "pdf_url": "https://cora.ucc.ie/bitstream/handle/10468/3544/Quigley_Chapter.pdf?sequence=1&isAllowed=y",
        "version": "acceptedVersion"
    }

    # stephen hawking's thesis
    override_dict["10.17863/cam.11283"] = {
        "pdf_url": "https://www.repository.cam.ac.uk/bitstream/handle/1810/251038/PR-PHD-05437_CUDL2017-reduced.pdf?sequence=15&isAllowed=y",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1152/advan.00040.2005"] = {
        "pdf_url": "https://www.physiology.org/doi/pdf/10.1152/advan.00040.2005",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1016/j.chemosphere.2014.07.047"] = {
        "pdf_url": "https://manuscript.elsevier.com/S0045653514009102/pdf/S0045653514009102.pdf",
        "version": "submittedVersion"
    }

    # from email
    override_dict["10.4324/9780203900956"] = {}

    # from email
    override_dict["10.3810/psm.2010.04.1767"] = {
        "pdf_url": "http://cupola.gettysburg.edu/cgi/viewcontent.cgi?article=1014&context=healthfac",
        "version": "publishedVersion"
    }

    # from email, zenodo
    override_dict["10.1080/01650521.2018.1460931"] = {
        "metadata_url": "https://zenodo.org/record/1236622",
        "host_type_set": "repository",
        "version": "acceptedVersion"
    }

    # from email
    override_dict["10.3928/01477447-20150804-53"] = {}

    # from twitter
    override_dict["10.1103/physreva.97.013421"] = {
        "pdf_url": "https://arxiv.org/pdf/1711.10074.pdf",
        "version": "submittedVersion"
    }

    # from chorus
    override_dict["10.1103/physrevd.94.052011"] = {
        "pdf_url": "https://link.aps.org/accepted/10.1103/PhysRevD.94.052011",
        "version": "acceptedVersion"
    }
    override_dict["10.1063/1.4962501"] = {
        "pdf_url": "https://aip.scitation.org/doi/am-pdf/10.1063/1.4962501",
        "version": "acceptedVersion"
    }

    # from email, broken citeseer link
    override_dict["10.2202/1949-6605.1908"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.535.9289&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1561/1500000012"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.174.8814&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    return override_dict
