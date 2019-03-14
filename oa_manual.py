from collections import defaultdict

from time import time
from util import elapsed
from util import clean_doi

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

    # from email, has bad citesserx cached version
    override_dict["10.1126/science.1150952"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.168.3796&rep=rep1&type=pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email, has bad citesserx cached version
    override_dict["10.1515/eqc.2007.295"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.543.7752&rep=rep1&type=pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
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

    # from email
    override_dict["10.1016/S0140-6736(17)33308-1"] = {
        "pdf_url": "https://www.rug.nl/research/portal/files/64097453/Author_s_version_Gonadotrophins_versus_clomiphene_citrate_with_or_without_intrauterine_insemination_in_women.pdf",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1093/joclec/nhy009"] = {
        "pdf_url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3126848",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1038/s41477-017-0019-3"] = {
        "pdf_url": "https://www.repository.cam.ac.uk/bitstream/handle/1810/270235/3383_1_merged_1502805167.pdf?sequence=1&isAllowed=y",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1029/wr015i006p01633"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.475.497&rep=rep1&type=pdf",
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

    # from email
    override_dict["10.1016/j.amjmed.2005.09.031"] = {
        "pdf_url": "https://www.amjmed.com/article/S0002-9343(05)00885-5/pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1080/15348458.2017.1327816"] = {}

    # from chorus
    override_dict["10.1103/physrevd.94.052011"] = {
        "pdf_url": "https://link.aps.org/accepted/10.1103/PhysRevD.94.052011",
        "version": "acceptedVersion",
    }
    override_dict["10.1063/1.4962501"] = {
        "pdf_url": "https://aip.scitation.org/doi/am-pdf/10.1063/1.4962501",
        "version": "acceptedVersion",
        "host_type_set": "repository"
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

    # from email
    override_dict["10.1137/s0036142902418680"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.144.7627&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1088/1741-2552/aab4e4"] = {
        "pdf_url": "http://iopscience.iop.org/article/10.1088/1741-2552/aab4e4/pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1145/1031607.1031615"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.540.8125&rep=rep1&type=pdf",
        "version": "publishedVersion"
    }

    # from email
    override_dict["10.1007/s11227-016-1779-7"] = {
        "pdf_url": "https://hcl.ucd.ie/system/files/TJS-Hasanov-2016.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1016/s0020-0190(03)00351-x"] = {
        "pdf_url": "https://kam.mff.cuni.cz/~kolman/papers/noteb.ps",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1002/14651858.cd001704.pub4"] = {
        "pdf_url": "https://core.ac.uk/download/pdf/9440822.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1016/j.tetlet.2015.04.131"] = {
        "pdf_url": "https://www.sciencedirect.com/sdfe/pdf/download/read/aam/noindex/pii/S0040403915007881",
        "version": "acceptedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1016/j.nima.2016.04.104"] = {
        "pdf_url": "http://cds.cern.ch/record/2239750/files/1-s2.0-S0168900216303400-main.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1016/s1470-2045(15)00444-1"] = {
        "pdf_url": "https://www.statsarecool.com/data/uploads/journal-articles/who_declares_reds_meat_carcinogeniclancet_oct_2015.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1056/NEJM199406233302502"] = {
        "pdf_url": "https://www.nejm.org/doi/full/10.1056/NEJM199406233302502",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1056/NEJMra1201534"] = {
        "pdf_url": "https://www.nejm.org/doi/pdf/10.1056/NEJMra1201534",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1016/j.cmet.2018.03.012"] = {
        "pdf_url": "https://www.biorxiv.org/content/biorxiv/early/2018/01/15/245332.full.pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1093/sf/65.1.1"] = {
        "pdf_url": "https://faculty.washington.edu/charles/new%20PUBS/A52.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1088/1751-8121/aabd9c"] = {}

    # from email
    override_dict["10.1017/CBO9781139173728.002"] = {}

    # from email
    override_dict["10.2174/97816810846711170101"] = {}

    # from email
    override_dict["10.1177/1354066196002003001"] = {}

    # from email
    override_dict["10.1093/bioinformatics/bty721"] = {}

    # from email
    override_dict["10.1088/1361-6528/aac7a4"] = {}

    # from email
    override_dict["10.1088/1361-6528/aac645"] = {}

    # from email
    override_dict["10.1111/1748-8583.12159"] = {}

    # from email
    override_dict["10.1042/BJ20080963"] = {}

    # from email
    override_dict["10.1136/bmj.j5007"] = {}

    # from email
    override_dict["10.1016/j.phrs.2017.12.007"] = {}

    # from email
    override_dict["10.4324/9781315770185"] = {}

    # from email
    override_dict["10.1108/PIJPSM-02-2016-0019"] = {}

    # from email
    override_dict["10.1016/j.ejca.2017.07.015"] = {}

    # from email
    override_dict["10.1080/14655187.2017.1469322"] = {}

    # from email
    override_dict["10.1080/02684527.2017.1407549"] = {}

    # from email
    override_dict["10.1093/jat/bky025"] = {}

    # from email
    override_dict["10.1016/j.midw.2009.07.004"] = {}

    # from email
    override_dict["10.1177/247553031521a00105"] = {}

    # from email
    override_dict["10.1002/0471445428"] = {}

    # from email
    override_dict["10.1007/978-3-642-31232-8"] = {}

    # ticket 267
    override_dict["10.1016/j.anucene.2014.08.021"] = {}

    # from email
    override_dict["10.1016/S0022-1996(00)00093-3"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.475.3874&rep=rep1&type=pdf",
        "version": "submittedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1177/088840649401700203"] = {
        "pdf_url": "http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.1014.8577&rep=rep1&type=pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.7326/L18-0139"] = {
        "pdf_url": "http://annals.org/data/journals/aim/936928/aime201804170-l180139.pdf",
        "version": "publishedVersion",
        "host_type_set": "publisher"
    }

    # from email
    override_dict["10.1007/978-3-319-48881-3_55"] = {
        "pdf_url": "http://liu.diva-portal.org/smash/get/diva2:1063949/FULLTEXT01.pdf",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1109/ICCVW.2015.86"] = {
        "pdf_url": "http://liu.diva-portal.org/smash/get/diva2:917646/FULLTEXT01",
        "version": "acceptedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1126/science.aap9559"] = {
        "pdf_url": "http://vermontcomplexsystems.org/share/papershredder/vosoughi2018a.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # from email
    override_dict["10.1109/tpds.2012.97"] = {
        "pdf_url": "https://www.cnsr.ictas.vt.edu/publication/06171175.pdf",
        "version": "publishedVersion",
        "host_type_set": "repository"
    }

    # the use of this is counting on the doi keys being lowercase/cannonical
    response = {}
    for k, v in override_dict.iteritems():
        response[clean_doi(k)] = v

    return response
