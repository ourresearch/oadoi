import unittest
from test.utils import open_file_from_data_dir
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
from nose.tools import assert_items_equal

from article import Article
from biblio import Biblio
import refset

from Bio import Medline
import os

handle = open_file_from_data_dir("medline_dump_3months_1journal.txt")
records_3months_1journal = list(Medline.parse(handle))


class TestRefsets(unittest.TestCase):

    def test_refset_percentile(self):
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
        a = Article(pmid, Biblio(medline_dump), raw_refset_dict)

        assert_equals(a.percentile, 67)



    def test_refset_percentile_for_incomplete_citations(self):
        raw_refset_dict = {
            "i_am_the_owner_pmid": 22,
            "refset_pmid1": "None"
        }
        a = Article("i_am_the_owner_pmid", Biblio({}), raw_refset_dict)
        assert_equals(a.percentile, None)        


    def test_refset_percentile_for_no_refset(self):
        raw_refset_dict = {
            "i_am_the_owner_pmid": 2
        }
        a = Article("i_am_the_owner_pmid", Biblio({}), raw_refset_dict)
        assert_equals(a.percentile, None)        


    def test_refset_percentile_for_incomplete_self_citations(self):
        raw_refset_dict = {
            "i_am_the_owner_pmid": "None"
        }
        a = Article("i_am_the_owner_pmid", Biblio({}), raw_refset_dict)
        assert_equals(a.percentile, None)  


    def test_get_closest_pmids(self):
        possible_biblios = [Biblio(record) for record in records_3months_1journal]
        response = refset.get_closest_biblios(
            possible_biblios, 
            "2013-01-23", 
            10)
        dates = [(biblio.pmid, biblio.best_pub_date) for biblio in response]
        expected = [('23352416', '2013-01-23T00:00:00+00:00'), ('23352126', '2013-01-24T00:00:00+00:00'), ('23375636', '2013-01-31T00:00:00+00:00'), ('23328477', '2013-01-14T00:00:00+00:00'), ('23328479', '2013-01-14T00:00:00+00:00'), ('23328478', '2013-01-14T00:00:00+00:00'), ('23328480', '2013-01-14T00:00:00+00:00'), ('23328481', '2013-01-14T00:00:00+00:00'), ('23328482', '2013-01-14T00:00:00+00:00'), ('23447819', '2013-01-14T00:00:00+00:00')]
        assert_items_equal(dates, expected)


    def test_tabulate_biblios_by_pub_date(self):
        possible_biblios = [Biblio(record) for record in records_3months_1journal]
        pseudo_date_biblios = refset.tabulate_biblios_by_pub_date(possible_biblios)
        publication_date_keys = pseudo_date_biblios.keys()
        expected = ['2013-01-14T00:00:00+00:00', '2013-02-11T00:00:00+00:00', '2013-03-18T00:00:00+00:00']
        assert_items_equal(publication_date_keys, expected)

        biblios_on_first_date = pseudo_date_biblios['2013-01-14T00:00:00+00:00']
        pmids_on_first_date = [biblio.pmid for biblio in biblios_on_first_date]
        expected = ['23447819', '23328482', '23328481', '23328480', '23328479', '23328478', '23328477']
        assert_items_equal(pmids_on_first_date, expected)


    def test_timedelta_between(self):
        date1 = "2012-01-01"
        date2 = "2012-01-15"
        response = refset.timedelta_between(date1, date2)
        expected = "-14 days, 0:00:00"
        print str(response)
        assert_equals(str(response), expected)


    def test_set_pseudo_dates_epub_unchanged(self):
        possible_biblios = [Biblio(record) for record in records_3months_1journal]
        pseudo_date_biblios = refset.set_pseudo_dates(possible_biblios)

        for biblio in pseudo_date_biblios:
            if biblio.has_epub_date:
                assert_equals(biblio.epub_date, biblio.pseudo_date)


    def test_set_pseudo_dates_pub_first_dates_unchanged(self):
        possible_biblios = [Biblio(record) for record in records_3months_1journal]
        pseudo_date_biblios = refset.set_pseudo_dates(possible_biblios)
        first_date = min([biblio.pub_date for biblio in possible_biblios])

        for biblio in pseudo_date_biblios:
            if not biblio.has_epub_date:
                # can't spread things out if is the first date
                if biblio.pub_date==first_date:
                    assert_equals(biblio.pub_date, biblio.pseudo_date)


    def test_set_pseudo_dates_pub_check_changed(self):
        possible_biblios = [Biblio(record) for record in records_3months_1journal]
        pseudo_date_biblios = refset.set_pseudo_dates(possible_biblios)
        unique_pub_dates = []
        unique_pseudo_dates = []
        pub_dates_when_no_epub = [biblio.pub_date for biblio in possible_biblios if not biblio.has_epub_date]
        first_date = min(pub_dates_when_no_epub)
        num_unique_pub_dates_before = len(set(pub_dates_when_no_epub))

        for biblio in pseudo_date_biblios:
            if not biblio.has_epub_date:
                if biblio.pub_date != first_date:
                    unique_pub_dates.append(biblio.pub_date)
                    unique_pseudo_dates.append(biblio.pseudo_date)
        num_pubs_after_first = len(unique_pub_dates)
        num_unique_pub_dates = len(set(unique_pub_dates))
        num_unique_pseudo_dates = len(set(unique_pseudo_dates))

        assert_equals(num_unique_pub_dates, num_unique_pub_dates_before - 1) 
        assert_equals(num_pubs_after_first, num_unique_pseudo_dates)

