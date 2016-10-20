import unittest
from nose.tools import nottest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
import requests
from ddt import ddt, data
import requests_cache

import product

requests_cache.install_cache('oadoa_requests_cache', expire_after=60*60*24*7)  # expire_after is in seconds

open_dois_from_juan = ['10.1002/cncr.30235',
 '10.1007/s00117-016-0151-5',
 '10.1016/s0140-6736(15)01087-9',
 '10.1016/s0140-6736(16)30825-x',
 '10.1038/mt.2016.119',
 '10.1038/nature.2016.20302',
 '10.1038/nutd.2016.20',
 '10.1038/srep29901',
 '10.1056/nejmoa1509388',
 '10.1056/nejmoa1516192',
 '10.1056/nejmoa1606220',
 '10.1136/bmj.i1209',
 '10.1136/bmj.i2716',
 '10.1186/s12885-016-2505-9',
 '10.1186/s12995-016-0127-4',
 '10.1364/boe.7.003795',
 '10.1371/journal.pone.0153011',
 '10.15585/mmwr.rr6501e1',
 '10.17061/phrp2641646',
 '10.18632/oncotarget.10653',
 '10.2147/jpr.s97759',
 '10.3322/caac.21332',
 '10.3322/caac.21338',
 # '10.3791/54429',  # this is jove and it looks closed to me
 '10.4103/1817-1737.185755']


closed_dois_from_juan = ['10.1002/pon.4156',
 '10.1016/j.cmet.2016.04.004',
 '10.1016/j.urolonc.2016.07.016',
 '10.1016/s0140-6736(16)30383-x',
 '10.1016/s2213-2600(15)00521-4',
 '10.1038/nature18300',
 '10.1038/ncb3399',
 '10.1056/nejmoa1600249',
 '10.1056/nejmoa1603144',
 '10.1080/03007995.2016.1198312',
 '10.1093/annonc/mdw322',
 '10.1093/jnci/djw035',
 '10.1093/pm/pnw115',
 '10.1111/add.13477',
 '10.1126/science.aad2149',
 '10.1126/science.aaf1490',
 '10.1136/bjsports-2016-096194',
 '10.1136/bmj.i788',
 '10.1136/jech-2015-207002',
 '10.1136/thoraxjnl-2016-208967',
 '10.1148/radiol.2016151419',
 '10.1158/1055-9965.epi-15-0924',
 '10.1158/1535-7163.mct-15-0846',
 '10.1177/0272989x15626384']


open_urls_from_scrape_tests = ['http://doi.org/10.1002/meet.2011.14504801327',
 'http://doi.org/10.1111/ele.12587',
 'http://doi.org/10.1136/bmj.i1209',
 'http://doi.org/10.1136/bmj.i2716',
 'http://dro.dur.ac.uk/1241/',
 'http://eprints.whiterose.ac.uk/77866/',
 'http://handle.unsw.edu.au/1959.4/unsworks_38708',
 'http://hdl.handle.net/10088/17542',
 'http://hdl.handle.net/1893/372',
 'http://hdl.handle.net/2060/20140010374',
 'http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6740844',
 'http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/abstract',
 'http://onlinelibrary.wiley.com/doi/10.1111/tpj.12616/abstract',
 'http://ro.uow.edu.au/aiimpapers/269/',
 'http://www.emeraldinsight.com/doi/full/10.1108/00251740510597707',
 'https://lirias.kuleuven.be/handle/123456789/372010',
 'https://research-repository.st-andrews.ac.uk/handle/10023/7421',
 'https://works.bepress.com/ethan_white/45/']

closed_urls_from_scrape_tests = ['http://doi.org/10.1007/s10822-012-9571-0',
 'http://doi.org/10.1038/nature16932',
 'http://doi.org/10.1038/ncb3399',
 'http://doi.org/10.1111/ele.12585',
 'http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6045214',
 'http://onlinelibrary.wiley.com/doi/10.1162/10881980152830079/abstract',
 'http://www.emeraldinsight.com/doi/abs/10.1108/14777261111143545',
 'http://www.sciencedirect.com/science/article/pii/S0147651300920050',
 'https://works.bepress.com/ethan_white/27/']



########### ones we still get wrong

# closed ones from juan that we say are open
 # '10.1016/s0140-6736(15)01156-3',
 # '10.1016/s0140-6736(16)00577-8',
 # '10.1016/s0140-6736(16)30370-1',
 # '10.1016/s0140-6736(16)30579-7',
 # '10.1038/nature16932',


# this is my nature paper, it is open on figshare
# http://doi.org/10.1038/493159a
# and listed on base https://www.base-search.net/Record/ed64a4b151d7f2fd9d68f0c81c747af73af84d2e13b77dfd9821b8980a23a9f1/

# this one is wrong, it returns with a bogus fulltext url
# http://localhost:5000/v1/publication?url=http://europepmc.org/abstract/med/18998885

# closed JAMA from juan.  causes timeouts.
# 10.1001/jamainternmed.2016.1615
# 10.1001/jamapsychiatry.2016.2387
# 10.1001/jama.2016.4666
# 10.1001/jamaoncol.2016.0843
# 10.1001/jamaophthalmol.2016.1139

# open JAMA from juan, but timeouts and we get them wrong
# 10.1001/jama.2016.5989
# 10.1001/jamaoncol.2016.1025
# 10.1001/jama.2016.1712


def guts(biblio):
    use_cache = False
    my_collection = product.run_collection_from_biblio(use_cache, **biblio)
    my_product = my_collection.products[0]
    return my_product


@ddt
class MyTestCase(unittest.TestCase):
    _multiprocess_can_split_ = True

    @data(*open_dois_from_juan)
    def test_has_fulltext_from_juan(self, doi):
        biblio = {"doi": doi}
        my_product = guts(biblio)
        assert_equals(my_product.has_fulltext_url, True)

    @data(*closed_dois_from_juan)
    def test_no_fulltext_from_juan(self, doi):
        biblio = {"doi": doi}
        my_product = guts(biblio)
        assert_equals(my_product.has_fulltext_url, False)

    @data(*open_urls_from_scrape_tests)
    def test_has_fulltext_url(self, url):
        biblio = {"url": url}
        my_product = guts(biblio)
        assert_equals(my_product.has_fulltext_url, True)

    @data(*closed_urls_from_scrape_tests)
    def test_no_fulltext_url(self, url):
        biblio = {"url": url}
        my_product = guts(biblio)
        assert_equals(my_product.has_fulltext_url, False)

    def test_figshare(self):
        biblio = {"doi": "10.6084/m9.figshare.94318"}
        my_product = guts(biblio)
        expected = "http://doi.org/10.6084/m9.figshare.94318"
        assert_equals(my_product.fulltext_url, expected)

    def test_returns_pmc(self):
        biblio = {"doi": "10.1111/j.1461-0248.2009.01305.x"}
        my_product = guts(biblio)
        expected = "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC2886595"
        assert_equals(my_product.fulltext_url, expected)

    def test_returns_journal_pdf(self):
        biblio = {"doi": "10.1086/592402"}
        my_product = guts(biblio)
        print my_product.to_dict()
        expected = "http://www.journals.uchicago.edu/doi/pdfplus/10.1086/592402"
        assert_equals(my_product.fulltext_url, expected)

    def test_europepmc_abstract(self):
        biblio = {"url": "http://europepmc.org/abstract/med/18998885"}
        my_product = guts(biblio)
        assert_equals(my_product.has_fulltext_url, False)
