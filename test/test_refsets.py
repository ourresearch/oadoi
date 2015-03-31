import unittest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
from nose.tools import assert_items_equal

from article import Article



class TestRefsets(unittest.TestCase):

    def test_refset_calculation(self):
        pmid = "i_am_the_owner_pmid"
        medline_dump = {
            "pmid": pmid
        }
        raw_refset_dict = {
            "refset_pmid1": 1,
            "refset_pmid2": 2,
            "refset_pmid3": 3,
            "i_am_the_owner_pmid": 2,
            }
        a = Article(pmid, medline_dump, raw_refset_dict)

        assert_equals(a.percentile, 67)



    def test_refset_calculation_for_incomplete_citations(self):
        raw_refset_dict = {
            "i_am_the_owner_pmid": 22,
            "refset_pmid1": "None"
        }
        a = Article("i_am_the_owner_pmid", {}, raw_refset_dict)
        assert_equals(a.percentile, None)        


    def test_refset_calculation_for_no_refset(self):
        raw_refset_dict = {
            "i_am_the_owner_pmid": 2
        }
        a = Article("i_am_the_owner_pmid", {}, raw_refset_dict)
        assert_equals(a.percentile, None)        


    def test_refset_calculation_for_incomplete_self_citations(self):
        raw_refset_dict = {
            "i_am_the_owner_pmid": "None"
        }
        a = Article("i_am_the_owner_pmid", {}, raw_refset_dict)
        assert_equals(a.percentile, None)  


