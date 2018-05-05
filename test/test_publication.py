import unittest
from nose.tools import nottest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
import requests
from ddt import ddt, data
import requests_cache

import pub
from app import logger
from util import clean_doi


requests_cache.install_cache('oadoa_requests_cache', expire_after=60*60*24*7)  # expire_after is in seconds

# run default open and closed like this:
# nosetests --processes=50 --process-timeout=600 test/

# test just hybrid like this
# nosetests --processes=50 --process-timeout=600 -s test/test_publication.py:TestHybrid

# test just active one like this
# nosetests --processes=50 --process-timeout=600 -s test/test_publication.py:TestActive


# to test hybrid code, comment back in the tests at the bottom of the file, and run again.



open_dois = [
    # gold or hybrid (no scraping required)
    ("10.1016/s0140-6736(15)01087-9", "https://doi.org/10.1016/s0140-6736(15)01087-9", "cc-by"),
    ("10.1016/s0140-6736(16)30825-x", "https://doi.org/10.1016/s0140-6736(16)30825-x", "cc-by"),
    ("10.1038/nutd.2016.20", "http://www.nature.com/nutd/journal/v6/n7/pdf/nutd201620a.pdf", "cc-by"),
    ("10.1038/srep29901", "http://www.nature.com/articles/srep29901.pdf", "cc-by"),
    ("10.1186/s12995-016-0127-4", "https://occup-med.biomedcentral.com/track/pdf/10.1186/s12995-016-0127-4?site=occup-med.biomedcentral.com", "cc-by"),
    ("10.1371/journal.pone.0153011", "https://doi.org/10.1371/journal.pone.0153011", "cc-by"),
    ("10.17061/phrp2641646", "http://www.phrp.com.au/wp-content/uploads/2016/09/PHRP-Mesothelioma-26416461.pdf", "cc-by-nc-sa"),
    ("10.2147/jpr.s97759", "https://www.dovepress.com/getfile.php?fileID=31485", "cc-by-nc"),
    ("10.4103/1817-1737.185755", "https://doi.org/10.4103/1817-1737.185755", "cc-by-nc-sa"),
    ("10.1016/0001-8708(91)90003-P", "https://doi.org/10.1016/0001-8708(91)90003-p", "elsevier-specific: oa user license"),

    # pmc or arxiv but other copies trump its version
    ("10.1038/mt.2016.119", "https://doi.org/10.1038/mt.2016.119", None),
    ("10.1056/nejmoa1516192", "https://air.unimi.it/bitstream/2434/423313/2/Genomic%20classif%20%26%20prognosis%20in%20AML.pdf", None),
    ("10.1158/1055-9965.epi-15-0924", "http://cebp.aacrjournals.org/content/cebp/25/4/634.full.pdf", None),
    ("10.1101/gad.284166.116", "http://genesdev.cshlp.org/content/30/13/1542.full.pdf", None),
	["10.1103/physreva.63.022114", "https://authors.library.caltech.edu/1967/1/NIEpra01.pdf", None],
	["10.1103/physrevlett.86.5184", "https://authors.library.caltech.edu/1966/1/NIEprl01.pdf", None],
	["10.1103/physreva.64.052309", "https://authors.library.caltech.edu/1989/1/BECpra01.pdf", None],
	["10.1103/physreva.68.052311", "https://authors.library.caltech.edu/76192/2/PhysRevA.68.052311.pdf", None],
	["10.1103/physreva.69.052316", "https://authors.library.caltech.edu/75914/2/PhysRevA.69.052316.pdf", None],
	["10.1103/physreva.71.032318", "http://espace.library.uq.edu.au/view/UQ:76022/UQ76022.pdf", None],
	["10.1103/physreva.73.052306", "http://espace.library.uq.edu.au/view/UQ%3A80529/UQ80529.pdf", None],
	["10.1103/physrevlett.97.110501", "http://espace.library.uq.edu.au/view/UQ:81219/UQ81219.pdf", None],
	["10.1103/physreva.57.4153", "https://authors.library.caltech.edu/1971/1/BARpra98.pdf", None],
	["10.1103/physrevlett.79.2915", "https://authors.library.caltech.edu/2019/1/NIEprl97a.pdf", None],
	["10.1103/physreva.61.064301", "https://authors.library.caltech.edu/1969/1/NIEpra01a.pdf", None],
	["10.1103/physreva.62.052308", "https://authors.library.caltech.edu/1965/1/NIEpra00b.pdf", None],
    ["10.1103/physreva.62.012304", "http://espace.library.uq.edu.au/view/UQ:250373/UQ250373_OA.pdf", None],

    # pmc
    ("10.1016/s2213-2600(15)00521-4", "http://europepmc.org/articles/pmc4752870?pdf=render", None),
    ("10.1056/nejmoa1603144", "http://europepmc.org/articles/pmc4986616?pdf=render", None),
    ("10.1126/science.aad2149", "http://europepmc.org/articles/pmc4849557?pdf=render", None),
    ("10.1126/science.aaf1490", "http://europepmc.org/articles/pmc4984254?pdf=render", None),
    ("10.1111/j.1461-0248.2009.01305.x", "http://europepmc.org/articles/pmc2886595?pdf=render", None),
    ("10.1038/nature12873", "http://europepmc.org/articles/pmc3944098?pdf=render", None),
    ("10.1038/nphoton.2015.151", "http://europepmc.org/articles/pmc4591469?pdf=render", None),

    # arxiv
	["10.1103/physrevlett.89.247902", "http://arxiv.org/pdf/quant-ph/0207072", None],
	["10.1088/0305-4470/34/35/324", "http://arxiv.org/pdf/quant-ph/0011063", None],
	["10.1103/physreva.78.032327", "http://arxiv.org/pdf/0808.3212", None],
	["10.1016/j.physd.2008.12.016", "http://arxiv.org/pdf/0809.0151", None],
	["10.1103/physreva.65.040301", "http://arxiv.org/pdf/quant-ph/0106064", None],
	["10.1103/physreva.65.062312", "http://arxiv.org/pdf/quant-ph/0112097", None],
	["10.1103/physreva.66.032110", "http://arxiv.org/pdf/quant-ph/0202162", None],
	["10.1016/s0375-9601(02)01272-0", "http://arxiv.org/pdf/quant-ph/0205035", None],
	["10.1103/physreva.67.052301", "http://arxiv.org/pdf/quant-ph/0208077", None],
	["10.1103/physrevlett.91.210401", "http://arxiv.org/pdf/quant-ph/0303022", None],
	["10.1103/physrevlett.90.193601", "http://arxiv.org/pdf/quant-ph/0303038", None],
	["10.1103/physreva.69.012313", "http://arxiv.org/pdf/quant-ph/0307148", None],
	["10.1103/physreva.69.032303", "http://arxiv.org/pdf/quant-ph/0308083", None],
	["10.1103/physrevlett.93.040503", "http://arxiv.org/pdf/quant-ph/0402005", None],
	["10.1103/physreva.71.052312", "http://arxiv.org/pdf/quant-ph/0405115", None],
	["10.1103/physreva.71.042323", "http://arxiv.org/pdf/quant-ph/0405134", None],
	["10.1103/physreva.71.062310", "http://arxiv.org/pdf/quant-ph/0408063", None],
	["10.1016/s0034-4877(06)80014-5", "http://arxiv.org/pdf/quant-ph/0504097", None],
	["10.1103/physreva.72.052332", "http://arxiv.org/pdf/quant-ph/0505139", None],
	["10.1103/physreva.75.064304", "http://arxiv.org/pdf/quant-ph/0506069", None],
	["10.1103/physrevlett.96.020501", "http://arxiv.org/pdf/quant-ph/0509060", None],
	["10.1103/physreva.73.062323", "http://arxiv.org/pdf/quant-ph/0603160", None],
	["10.1126/science.1121541", "http://arxiv.org/pdf/quant-ph/0603161", None],
	["10.1103/physreva.55.2547", "http://arxiv.org/pdf/quant-ph/9608001", None],
	["10.1103/physreva.56.2567", "http://arxiv.org/pdf/quant-ph/9704002", None],
	["10.1109/18.850671", "http://arxiv.org/pdf/quant-ph/9809010", None],
	["10.1103/physrevlett.79.321", "http://arxiv.org/pdf/quant-ph/9703032", None],
	["10.1103/physreva.54.2629", "http://arxiv.org/pdf/quant-ph/9604022", None],

    # manual
  	["10.1098/rspa.1998.0160", "https://arxiv.org/pdf/quant-ph/9706064.pdf", None],


    # other green
    ("10.1038/nature02453","http://epic.awi.de/10127/1/Eng2004b.pdf",None),
    # ("10.1109/tc.2002.1039844",None,None),

    # manual overrides
    ("10.1038/nature21360", "https://arxiv.org/pdf/1703.01424.pdf", None),
    ("10.1021/acs.jproteome.5b00852", "http://pubs.acs.org/doi/pdfplus/10.1021/acs.jproteome.5b00852", None)

    # not sure what to do about noncrossref right now
    # ("10.6084/m9.figshare.94318", "https://doi.org/10.6084/m9.figshare.94318", None),

    # not working right now
    # ("10.1001/archderm.143.11.1372", "http://espace.library.uq.edu.au/view/UQ:173337/UQ173337_OA.pdf", None),
    # ("10.1186/s12885-016-2505-9", "https://doi.org/10.1186/s12885-016-2505-9", "cc-by"),
    # ("10.1039/b310394c","https://www.era.lib.ed.ac.uk/bitstream/1842/903/1/ChemComm_24_2003.pdf",None),
    # ("10.1021/jp304817u","http://www.tara.tcd.ie/bitstream/2262/72320/1/MS244-Tara.pdf",None),
    # ("10.1016/0167-2789(84)90086-1","http://projecteuclid.org/download/pdf_1/euclid.cmp/1103941232",None),

    ]


closed_dois = [
    ("10.1002/pon.4156", None, None),
    ("10.1016/j.cmet.2016.04.004", None, None),
    ("10.1016/j.urolonc.2016.07.016", None, None),
    ("10.1016/s0140-6736(16)30383-x", None, None),
    ("10.1038/nature18300", None, None),
    ("10.1038/ncb3399", None, None),
    ("10.1056/nejmoa1600249", None, None),
    ("10.1080/03007995.2016.1198312", None, None),
    ("10.1093/annonc/mdw322", None, None),
    ("10.1093/jnci/djw035", None, None),
    ("10.1093/pm/pnw115", None, None),
    ("10.1111/add.13477", None, None),
    ("10.1136/bmj.i788", None, None),
    ("10.1136/thoraxjnl-2016-208967", None, None),
    ("10.1148/radiol.2016151419", None, None),
    ("10.1177/0272989x15626384", None, None),
    ("10.1002/wsb.128", None, None),  # should be PD but is actually paywalled on the publisher site
    ("10.1021/acs.jafc.6b02480", None, None),
    ("10.3354/meps09890", None, None),  # has a stats.html link
    ("10.1002/ev.20003", None, None),
    ("10.1001/archderm.143.11.1456", None, None),  # there is PMC hit with the same title but not correct match because authors
    ("10.1016/0370-2693(82)90526-3", None, None),  # gold doaj journal but it turned OA afterwards
	["10.1016/j.physd.2009.12.001", None, None],
	["10.1038/nphys1238", None, None],
]





@ddt
class TestNonHybrid(unittest.TestCase):
    _multiprocess_can_split_ = True

    @data(*open_dois)
    def test_open_dois(self, test_data):
        (doi, fulltext_url, license) = test_data
        my_pub = pub.lookup_product_by_doi(doi)
        my_pub.recalculate()

        logger.info(u"was looking for {}, got {}\n\n".format(fulltext_url, my_pub.fulltext_url))
        logger.info(u"https://api.unpaywall.org/v2/{}?email=me".format(doi))
        logger.info(u"doi: https://doi.org/{}".format(doi))
        logger.info(u"title: {}".format(my_pub.best_title))
        logger.info(u"evidence: {}\n\n".format(my_pub.evidence))
        if my_pub.error:
            logger.info(my_pub.error)

        assert_not_equals(my_pub.fulltext_url, None)
        assert_equals(fulltext_url, my_pub.fulltext_url)


    # @data(*closed_dois)
    # def test_closed_dois(self, test_data):
    #     (doi, fulltext_url, license) = test_data
    #     my_pub = pub.lookup_product_by_doi(doi)
    #     my_pub.recalculate()
    #
    #     logger.info(u"was looking for {}, got {}\n\n".format(fulltext_url, my_pub.fulltext_url))
    #     logger.info(u"doi: https://doi.org/{}".format(doi))
    #     logger.info(u"title: {}".format(my_pub.best_title))
    #     logger.info(u"evidence: {}\n\n".format(my_pub.evidence))
    #     if my_pub.error:
    #         logger.info(my_pub.error)
    #
    #     assert_equals(my_pub.fulltext_url, None)
    #



# have to scrape the publisher pages to find these
hybrid_dois = [
    # Elsevier BV
    ["10.1016/j.bpj.2012.11.2487", "https://doi.org/10.1016/j.bpj.2012.11.2487", "elsevier-specific: oa user license", "blue"],
    ["10.1016/j.laa.2009.03.008", "https://doi.org/10.1016/j.laa.2009.03.008", "elsevier-specific: oa user license", "blue"],
    ["10.1016/s2213-8587(13)70033-0", "http://www.thelancet.com/article/S2213858713700330/pdf", None, "blue"],
    ["10.1016/j.compedu.2017.03.017", "http://www.sciencedirect.com/science/article/pii/S0360131517300726/pdfft?md5=ee1077bac521e4d909ffc2e4375ea3d0&pid=1-s2.0-S0360131517300726-main.pdf", None, "blue"],

    # Wiley-Blackwell
    ["10.1890/ES13-00330.1", "https://doi.org/10.1890/es13-00330.1", "cc-by", "gold"],
    ["10.1016/j.fob.2014.11.003", "https://doi.org/10.1016/j.fob.2014.11.003", "cc-by", "gold"],

    # Springer Science + Business Media
    ["10.1007/s13201-013-0144-8", "https://link.springer.com/content/pdf/10.1007%2Fs13201-013-0144-8.pdf", "cc-by", "blue"],
    ["10.1007/s11214-015-0153-z", "https://link.springer.com/content/pdf/10.1007%2Fs11214-015-0153-z.pdf", "cc-by", "blue"],

    # Informa UK Limited
    # which is (T&F)
    ["10.4161/psb.6.4.14908", "https://www.tandfonline.com/doi/pdf/10.4161/psb.6.4.14908?needAccess=true", None, "blue"],
    ["10.4161/rna.7.4.12301", "https://www.tandfonline.com/doi/pdf/10.4161/rna.7.4.12301?needAccess=true", None, "blue"],
    ["10.1080/00031305.2016.1154108", "https://www.tandfonline.com/doi/pdf/10.1080/00031305.2016.1154108?needAccess=true", None, "blue"],

    # SAGE Publications
    ["10.1177/2041731413519352", "http://journals.sagepub.com/doi/pdf/10.1177/2041731413519352", "cc-by-nc", "gold"],
    ["10.1177/1557988316669041", "http://journals.sagepub.com/doi/pdf/10.1177/1557988316669041", "cc-by-nc", "blue"],
    ["10.1177/1557988316665084", "http://journals.sagepub.com/doi/pdf/10.1177/1557988316665084", None, "blue"], #is just free

    # Ovid Technologies (Wolters Kluwer Health)
    ["10.1161/CIR.0000000000000066", "http://circ.ahajournals.org/content/129/25_suppl_2/S46.full.pdf", "cc-by-nc", "blue"],
    ["10.1161/ATVBAHA.115.305896", "http://atvb.ahajournals.org/content/atvbaha/35/9/1963.full.pdf", "cc-by", "blue"],
    # the session ids on these keep being different
    # ["10.1097/00003643-201406001-00238", "http://pdfs.journals.lww.com/ejanaesthesiology/2014/06001/Nonintubated_thoracoscopic_lobectomy_using.238.pdf?token=method|ExpireAbsolute;source|Journals;ttl|1496524564436;payload|mY8D3u1TCCsNvP5E421JYK6N6XICDamxByyYpaNzk7FKjTaa1Yz22MivkHZqjGP4kdS2v0J76WGAnHACH69s21Csk0OpQi3YbjEMdSoz2UhVybFqQxA7lKwSUlA502zQZr96TQRwhVlocEp/sJ586aVbcBFlltKNKo+tbuMfL73hiPqJliudqs17cHeLcLbV/CqjlP3IO0jGHlHQtJWcICDdAyGJMnpi6RlbEJaRheGeh5z5uvqz3FLHgPKVXJzdGZnEagBFgfcfP0kYnmKqypHHq6BvY5pwKneuY7A6dG2xuH9nJxba+Nr3/Wc9Iy69;hash|ZgAEzB9gUG6vWYyS1QKqqg==", None, "blue"],
    # ["10.1097/00007890-198506000-00009", "http://pdfs.journals.lww.com/transplantjournal/1985/06000/PROFOUND_HYPOMAGNESEMIA_AND_RENAL_MAGNESIUM.9.pdf?token=method|ExpireAbsolute;source|Journals;ttl|1496524563500;payload|mY8D3u1TCCsNvP5E421JYK6N6XICDamxByyYpaNzk7FKjTaa1Yz22MivkHZqjGP4kdS2v0J76WGAnHACH69s21Csk0OpQi3YbjEMdSoz2UhVybFqQxA7lKwSUlA502zQZr96TQRwhVlocEp/sJ586aVbcBFlltKNKo+tbuMfL73hiPqJliudqs17cHeLcLbV/CqjlP3IO0jGHlHQtJWcICDdAyGJMnpi6RlbEJaRheGeh5z5uvqz3FLHgPKVXJzdGlb2qsojlvlytk14LkMXSB6xCncFy3TAupSQD/bBWevI1dfjCGL0QTxuCx6zmVUq;hash|ILYxyuVGFUT0JjKt2gW0zA==", None, "blue"],

    # Oxford University Press (OUP)
    # ["10.1093/icvts/ivr077", "https://academic.oup.com/icvts/article-pdf/14/4/420/1935098/ivr077.pdf", None, "blue"],
    ["10.1093/icvts/ivs301", "https://academic.oup.com/icvts/article-pdf/16/1/31/17754118/ivs301.pdf", None, "blue"],

    # American Chemical Society (ACS)
    ["10.1021/ci025584y", "http://pubs.acs.org/doi/pdf/10.1021/ci025584y", "cc-by", "blue"],
    ["10.1021/acs.jctc.5b00407", "https://doi.org/10.1021/acs.jctc.5b00407", "acs-specific: authorchoice/editors choice usage agreement", "blue"],
    ["10.1021/ja808537j", "https://doi.org/10.1021/ja808537j", "acs-specific: authorchoice/editors choice usage agreement", "blue"],

    # Institute of Electrical & Electronics Engineers (IEEE)
    ["10.1109/JSTQE.2015.2473140", "https://doi.org/10.1109/jstqe.2015.2473140", None, "blue"],
    # ["10.1109/JSTQE.2015.2473140", "http://ieeexplore.ieee.org:80/stamp/stamp.jsp?tp=&arnumber=7225120", None, "blue"],
    # ["10.1109/TCBB.2016.2613040", "http://ieeexplore.ieee.org:80/stamp/stamp.jsp?tp=&arnumber=7581044", None, "blue"],
    ["10.1109/TCBB.2016.2613040", "https://doi.org/10.1109/tcbb.2016.2613040", None, "blue"],
    # ["10.1109/tdsc.2006.38", "http://ieeexplore.ieee.org:80/stamp/stamp.jsp?tp=&arnumber=1673385", None, "blue"],

    # Royal Society of Chemistry (RSC)
    ["10.1039/C3SM27341E", "http://pubs.rsc.org/en/content/articlepdf/2013/sm/c3sm27341e", None, "blue"],
    ["10.1039/C3CC38783F", "http://pubs.rsc.org/en/content/articlepdf/2013/cc/c3cc38783f", None, "blue"],

    # Cambridge University Press (CUP)
    ["10.1017/S0022046906008207", "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/4BCD306196706C82B0DDFDA7EC611BC7/S0022046906008207a.pdf/div-class-title-justification-by-faith-a-patristic-doctrine-div.pdf", None, "blue"],
    ["10.1017/S0890060400003140", "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/5E94996DC7939479313B8BDD299C586B/S0890060400003140a.pdf/div-class-title-optimized-process-planning-by-generative-simulated-annealing-div.pdf", None, "blue"],
    ["10.1017/erm.2017.7", "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/38E0CB06CD4CA6AA6BC70F2EAAE79CB2/S1462399417000072a.pdf/div-class-title-intracellular-delivery-of-biologic-therapeutics-by-bacterial-secretion-systems-div.pdf", None, "blue"],

    # IOP Publishing
    ["10.1088/1478-3975/13/6/066003", "https://doi.org/10.1088/1478-3975/13/6/066003", "cc-by", "blue"],
    ["10.1088/1757-899X/165/1/012032", "https://doi.org/10.1088/1757-899x/165/1/012032", "cc-by", "blue"],

    # Thieme Publishing Group
    # this one gives a DOI error for some reason
    # ["10.1055/s-0037-1601483", "http://www.thieme-connect.de/products/ejournals/pdf/10.1055/s-0037-1601483.pdf", "cc-by-nc-nd", "blue"],
    ["10.1055/s-0036-1597987", "http://www.thieme-connect.de/products/ejournals/pdf/10.1055/s-0036-1597987.pdf", "cc-by-nc-nd", "blue"],
    ["10.1055/s-0043-102400", "https://doi.org/10.1055/s-0043-102400", "cc-by-nc-nd", "gold"],

    # BMJ
    ["10.1136/tobaccocontrol-2012-050767", "http://tobaccocontrol.bmj.com/content/tobaccocontrol/22/suppl_1/i33.full.pdf", "cc-by-nc", "blue"],

    # Emerald
    ["10.1108/IJCCSM-04-2017-0089", "https://www.emeraldinsight.com/doi/pdfplus/10.1108/IJCCSM-04-2017-0089", "", ""],

    # Nature Publishing Group
    ["10.1038/427016b", "http://www.nature.com/nature/journal/v427/n6969/pdf/427016b.pdf", None, "blue"],
    ["10.1038/nmicrobiol.2016.48", "http://www.nature.com/articles/nmicrobiol201648.pdf", "cc-by", "blue"],
    ["10.1038/nature19106", "http://www.nature.com/nature/journal/v536/n7617/pdf/nature19106.pdf", None, "blue"],

    # JSTOR
    # American Physical Society (APS)
    # American Medical Association (AMA)
    # Walter de Gruyter GmbH
    # AIP Publishing
        # closed 10.1063/1.113376
        # open 10.1063/1.4954031  10.1063/1.4982238
    # University of Chicago Press

    # other
    ["10.1017/S0022046906008207", "https://www.cambridge.org/core/services/aop-cambridge-core/content/view/4BCD306196706C82B0DDFDA7EC611BC7/S0022046906008207a.pdf/div-class-title-justification-by-faith-a-patristic-doctrine-div.pdf", None, "blue"],
    ["10.1053/j.jvca.2012.06.008", "http://www.jcvaonline.com/article/S1053077012003126/pdf", None, "blue"],
    ["10.1086/101104", "https://doi.org/10.1086/101104", None, "blue"],
    ["10.1175/1520-0493(1917)45<614a:rafd>2.0.co;2", "http://docs.lib.noaa.gov/rescue/mwr/045/mwr-045-12-0614a.pdf", None, "blue"],
    ["10.2139/ssrn.128675", "http://ageconsearch.umn.edu/record/25010/files/wp010855.pdf", None, "green"],
    ["10.1016/j.juro.2011.02.760", "http://www.jurology.com/article/S0022534711010081/pdf", None, "blue"],
    ["10.1177/1078390309359685", "http://journals.sagepub.com/doi/pdf/10.1177/1078390309359685", None, "blue"],
    ["10.1053/j.gastro.2005.12.036", "http://www.gastrojournal.org/article/S001650850502576X/pdf", None, "blue"],
    ["10.1016/S1359-5113(07)00296-6", "http://www.sciencedirect.com/science/article/pii/S1359511307002966/pdfft?md5=07b777756218be2486a71a9182ebb234&pid=1-s2.0-S1359511307002966-main.pdf", None, "blue"],
    ["10.5575/geosoc.102.685", "https://www.jstage.jst.go.jp/article/geosoc1893/102/8/102_8_685/_pdf", None, "blue"],
    ["10.1111/nph.14052", "http://onlinelibrary.wiley.com/doi/10.1111/nph.14052/pdf", None, "blue"],
    # ["10.2298/sgs0603181l", "boo", None, "blue"],
    #
    # needs to follow javascript
    ["10.5762/kais.2016.17.5.316", "http://ocean.kisti.re.kr/downfile/volume/kivt/SHGSCZ/2016/v17n5/SHGSCZ_2016_v17n5_316.pdf", None, "blue"],
]



@ddt
class TestHybrid(unittest.TestCase):
    _multiprocess_can_split_ = True

    pass

    # nosetests --processes=50 --process-timeout=30 test/
    @data(*hybrid_dois)
    def test_hybrid_dois(self, test_data):

        (doi, fulltext_url, license, color) = test_data

        # because cookies breaks the cache pickling
        # for doi_start in ["10.1109", "10.1161", "10.1093", "10.1007", "10.1039"]:
        #     if doi.startswith(doi_start):
        requests_cache.uninstall_cache()

        my_pub = pub.lookup_product_by_doi(doi)
        my_pub.refresh()

        logger.info(u"\n\nwas looking for {}, got {}".format(fulltext_url, my_pub.fulltext_url))
        logger.info(u"https://api.unpaywall.org/v2/{}?email=me".format(doi))
        logger.info(u"doi: https://doi.org/{}".format(doi))
        logger.info(u"license: {}".format(my_pub.license))
        logger.info(u"oa_color: {}".format(my_pub.oa_color))
        logger.info(u"evidence: {}".format(my_pub.evidence))
        if my_pub.error:
            logger.info(my_pub.error)

        assert_equals(my_pub.error, "")
        assert_equals(my_pub.fulltext_url, fulltext_url)
        # assert_equals(my_pub.license, license)
        assert_equals(my_pub.error, "")



active_dois = [
    ["10.1108/IJCCSM-04-2017-0089", "https://www.emeraldinsight.com/doi/pdfplus/10.1108/IJCCSM-04-2017-0089", "", ""],
]


@ddt
class TestActive(unittest.TestCase):
    _multiprocess_can_split_ = True

    pass

    # nosetests --processes=50 --process-timeout=30 test/
    @data(*active_dois)
    def test_active_dois(self, test_data):

        (doi, fulltext_url, license, color) = test_data

        # because cookies breaks the cache pickling
        # for doi_start in ["10.1109", "10.1161", "10.1093", "10.1007", "10.1039"]:
        #     if doi.startswith(doi_start):
        # requests_cache.uninstall_cache()

        my_pub = pub.lookup_product_by_doi(doi)
        my_pub.refresh()

        logger.info(u"\n\nwas looking for {}, got {}".format(fulltext_url, my_pub.fulltext_url))
        logger.info(u"https://api.unpaywall.org/v2/{}?email=me".format(doi))
        logger.info(u"doi: https://doi.org/{}".format(doi))
        logger.info(u"license: {}".format(my_pub.license))
        logger.info(u"oa_color: {}".format(my_pub.oa_color))
        logger.info(u"evidence: {}".format(my_pub.evidence))
        if my_pub.error:
            logger.info(my_pub.error)

        assert_equals(my_pub.error, "")
        assert_equals(my_pub.fulltext_url, fulltext_url)
        assert_not_equals(my_pub.fulltext_url, None)
        # assert_equals(my_pub.license, license)
        assert_equals(my_pub.error, "")


