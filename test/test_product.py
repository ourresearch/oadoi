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

test_dois = [
    # open from juan
    ("10.1002/cncr.30235", "http://doi.org/10.1002/cncr.30235", "cc-by"),
    ("10.1007/s00117-016-0151-5", "http://link.springer.com/content/pdf/10.1007%2Fs00117-016-0151-5.pdf", "unknown"),
    ("10.1016/s0140-6736(15)01087-9", "http://doi.org/10.1016/s0140-6736(15)01087-9", "cc-by"),
    ("10.1016/s0140-6736(16)30825-x", "http://doi.org/10.1016/s0140-6736(16)30825-x", "cc-by"),
    ("10.1038/mt.2016.119", "http://www.nature.com/mt/journal/vaop/ncurrent/pdf/mt2016119a.pdf", "cc-by"),
    ("10.1038/nature.2016.20302", "http://www.nature.com:80/polopoly_fs/1.20302!/menu/main/topColumns/topLeftColumn/pdf/nature.2016.20302.pdf", "unknown"),
    ("10.1038/nutd.2016.20", "http://doi.org/10.1038/nutd.2016.20", "cc-by"),
    ("10.1038/srep29901", "http://doi.org/10.1038/srep29901", "cc-by"),
    ("10.1056/nejmoa1509388", "https://www.janssenmd.com/pdf/imbruvica/PI-Imbruvica.pdf", "unknown"),
    ("10.1056/nejmoa1516192", "http://www.nejm.org/doi/pdf/10.1056/NEJMoa1516192", "unknown"),
    ("10.1056/nejmoa1606220", "http://www.nejm.org/doi/pdf/10.1056/NEJMoa1606220", "unknown"),
    ("10.1136/bmj.i1209", "http://static.www.bmj.com/content/bmj/352/bmj.i1209.full.pdf", "cc-by-nc"),
    ("10.1136/bmj.i2716", "http://www.bmj.com/content/bmj/353/bmj.i2716.full.pdf", "cc-by"),
    ("10.1186/s12885-016-2505-9", "http://doi.org/10.1186/s12885-016-2505-9", "cc-by"),
    ("10.1186/s12995-016-0127-4", "http://doi.org/10.1186/s12995-016-0127-4", "cc-by"),
    ("10.1364/boe.7.003795", "http://doi.org/10.1364/boe.7.003795", "unknown"),
    ("10.1371/journal.pone.0153011", "http://doi.org/10.1371/journal.pone.0153011", "cc-by"),
    ("10.15585/mmwr.rr6501e1", "http://www.cdc.gov/mmwr/volumes/65/rr/pdfs/rr6501e1.pdf", "pd"),
    ("10.17061/phrp2641646", "http://doi.org/10.17061/phrp2641646", "cc-by-nc-sa"),
    ("10.18632/oncotarget.10653", "http://www.impactjournals.com/oncotarget/index.php?journal=oncotarget&page=article&op=download&path%5B%5D=10653&path%5B%5D=33731", "cc-by"),
    ("10.2147/jpr.s97759", "http://doi.org/10.2147/jpr.s97759", "cc-by-nc"),
    ("10.3322/caac.21332", "http://onlinelibrary.wiley.com/doi/10.3322/caac.21332/pdf", "unknown"),
    ("10.3322/caac.21338", "http://onlinelibrary.wiley.com/doi/10.3322/caac.21338/pdf", "unknown"),
    ("10.4103/1817-1737.185755", "http://doi.org/10.4103/1817-1737.185755", "cc-by-nc-sa"),

    # closed from juan
    ("10.1002/pon.4156", None, "unknown"),
    ("10.1016/j.cmet.2016.04.004", None, "unknown"),
    ("10.1016/j.urolonc.2016.07.016", None, "unknown"),
    ("10.1016/s0140-6736(16)30383-x", None, "unknown"),
    ("10.1016/s2213-2600(15)00521-4", None, "unknown"),
    ("10.1038/nature18300", None, "unknown"),
    ("10.1038/ncb3399", None, "unknown"),
    ("10.1056/nejmoa1600249", None, "unknown"),
    ("10.1056/nejmoa1603144", None, "unknown"),
    ("10.1080/03007995.2016.1198312", None, "unknown"),
    ("10.1093/annonc/mdw322", None, "unknown"),
    ("10.1093/jnci/djw035", None, "unknown"),
    ("10.1093/pm/pnw115", None, "unknown"),
    ("10.1111/add.13477", None, "unknown"),
    ("10.1126/science.aad2149", None, "unknown"),
    ("10.1126/science.aaf1490", None, "unknown"),
    ("10.1136/bjsports-2016-096194", None, "unknown"),
    ("10.1136/bmj.i788", None, "unknown"),
    ("10.1136/jech-2015-207002", None, "unknown"),
    ("10.1136/thoraxjnl-2016-208967", None, "unknown"),
    ("10.1148/radiol.2016151419", None, "unknown"),
    ("10.1158/1055-9965.epi-15-0924", None, "unknown"),
    ("10.1158/1535-7163.mct-15-0846", None, "unknown"),
    ("10.1177/0272989x15626384", None, "unknown"),

    # more examples that were broken at some point
    ("10.6084/m9.figshare.94318", "http://doi.org/10.6084/m9.figshare.94318", "cc-by"),
    ("10.1111/j.1461-0248.2009.01305.x", "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC2886595", "unknown"),
    ("10.1086/592402", "http://www.journals.uchicago.edu/doi/pdfplus/10.1086/592402", "unknown"),
    ("10.1002/wsb.128", None, "pd")

]


test_urls = [
    # open from scrape tests
    ("http://doi.org/10.1002/meet.2011.14504801327", "http://onlinelibrary.wiley.com/doi/10.1002/meet.2011.14504801327/pdf", "unknown"),
    ("http://doi.org/10.1111/ele.12587", "http://onlinelibrary.wiley.com/doi/10.1111/ele.12587/pdf", "cc-by"),
    ("http://doi.org/10.1136/bmj.i1209", "http://static.www.bmj.com/content/bmj/352/bmj.i1209.full.pdf", "cc-by-nc"),
    ("http://doi.org/10.1136/bmj.i2716", "http://www.bmj.com/content/bmj/353/bmj.i2716.full.pdf", "cc-by"),
    ("http://dro.dur.ac.uk/1241/", "http://dro.dur.ac.uk/1241/1/1241.pdf?DDD14+dgg1mbk+dgg0cnm", "unknown"),
    ("http://eprints.whiterose.ac.uk/77866/", "http://eprints.whiterose.ac.uk/77866/25/ggge20346_with_coversheet.pdf", "unknown"),
    ("http://hdl.handle.net/10088/17542", "https://repository.si.edu/bitstream/10088/17542/1/vz_McDade_et_al._2011_BioScience_assessment_.pdf", "unknown"),
    ("http://hdl.handle.net/1893/372", "http://dspace.stir.ac.uk/bitstream/1893/372/1/Corley%20COGNITION%202007.pdf", "unknown"),
    ("http://hdl.handle.net/2060/20140010374", "http://hdl.handle.net/2060/20140010374", "unknown"),
    ("http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6740844", "http://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=6740844", "unknown"),
    ("http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/abstract", "http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/pdf", "unknown"),
    ("http://onlinelibrary.wiley.com/doi/10.1111/tpj.12616/abstract", "http://onlinelibrary.wiley.com/doi/10.1111/tpj.12616/pdf", "unknown"),
    ("http://ro.uow.edu.au/aiimpapers/269/", "http://ro.uow.edu.au/cgi/viewcontent.cgi?article=1268&context=aiimpapers", "unknown"),
    ("http://www.emeraldinsight.com/doi/full/10.1108/00251740510597707", "http://www.emeraldinsight.com/doi/pdfplus/10.1108/00251740510597707", "unknown"),
    ("https://lirias.kuleuven.be/handle/123456789/372010", "https://lirias.kuleuven.be/handle/123456789/372010", "unknown"),
    ("https://research-repository.st-andrews.ac.uk/handle/10023/7421", "https://research-repository.st-andrews.ac.uk/bitstream/10023/7421/1/Manuscripts_edited_final.pdf", "unknown"),
    ("https://works.bepress.com/ethan_white/45/", "https://works.bepress.com/ethan_white/45/download/", "unknown"),

    # closed from scrape tests
    ("http://doi.org/10.1007/s10822-012-9571-0", None, "unknown"),
    ("http://doi.org/10.1038/nature16932", None, "unknown"),
    ("http://doi.org/10.1038/ncb3399", None, "unknown"),
    ("http://doi.org/10.1111/ele.12585", None, "unknown"),
    ("http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6045214", None, "unknown"),
    ("http://onlinelibrary.wiley.com/doi/10.1162/10881980152830079/abstract", None, "unknown"),
    ("http://www.emeraldinsight.com/doi/abs/10.1108/14777261111143545", None, "unknown"),
    ("http://www.sciencedirect.com/science/article/pii/S0147651300920050", None, "unknown"),
    ("https://works.bepress.com/ethan_white/27/", None, "unknown"),

    # more examples that were broken at some point
    ("http://europepmc.org/abstract/med/18998885", None, "unknown")

]



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

# 10.1002/ecy.1605
# is available in biorxiv here 10.1101/018861 but the biorxiv version not indexed in base.
# not sure why not, have dropped base a note.

def guts(biblio):
    use_cache = False
    my_collection = product.run_collection_from_biblio(use_cache, **biblio)
    my_product = my_collection.products[0]
    return my_product



@ddt
class MyTestCase(unittest.TestCase):
    _multiprocess_can_split_ = True

    @data(*test_dois)
    def test_dois(self, test_data):
        (doi, fulltext_url, license) = test_data
        biblio = {"doi": doi}
        my_product = guts(biblio)
        assert_equals(my_product.fulltext_url, fulltext_url)
        assert_equals(my_product.license, license)

    @data(*test_urls)
    def test_urls(self, test_data):
        (url, fulltext_url, license) = test_data
        biblio = {"url": url}
        my_product = guts(biblio)
        assert_equals(my_product.fulltext_url, fulltext_url)
        assert_equals(my_product.license, license)



# class MyTestCase2(unittest.TestCase):
#     _multiprocess_can_split_ = True
#     def test_print_out(self):
#         prints = ""
#         for doi in closed_urls_from_scrape_tests:
#             biblio = {"url": doi}
#             my_product = guts(biblio)
#             url_string = my_product.fulltext_url
#             if url_string:
#                 url_string = u'"{}"'.format(url_string)
#             prints += u'("{}", {}, "{}"),\n'.format(my_product.url, url_string, my_product.license)
#         print prints
#         assert_equals(1, 2)