import unittest
from nose.tools import nottest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
from nose.tools import assert_items_equal
from nose.tools import assert_in
from nose.tools import assert_not_in
from test.utils import setup_redis_for_unittests
from test.utils import open_file_from_data_dir

from test.data.medline_citations import medline_article
from test.data.medline_citations import medline_conference_paper

from biblio import Biblio

from Bio import Medline


class TestBiblio(unittest.TestCase):

    def setUp(self):
        pass

    def test_author_string(self):
        b = Biblio(medline_article)
        author_string = b.author_string
        assert_equals(
            author_string,
            'Piwowar HA, Becich MJ, Bilofsky H, Crowley RS'
        )
        b = Biblio(medline_conference_paper)
        author_string = b.author_string
        assert_equals(
            author_string,
            'Piwowar HA, Chapman WW'
        )


    def test_mesh_terms(self):
        b = Biblio(medline_article)
        mesh = b.mesh_terms
        assert_in(
            'Academic Medical Centers/*trends',
            mesh
        )


    def test_to_dict_without_args(self):
        b = Biblio(medline_article)
        b_dict = b.to_dict()

        assert_equals(
            b_dict["pmid"],
            '18767901'
        )

        assert_in(
            "abstract",
            b_dict.keys()
        )

    def test_to_dict_hide_keys(self):
        b = Biblio(medline_article)
        b_dict = b.to_dict(hide_keys=["title"])
        assert_not_in(
            "title",
            b_dict.keys()
        )
        assert_in(
            "journal",
            b_dict.keys()
        )


    def test_to_dict_show_keys(self):
        b = Biblio(medline_article)
        b_dict = b.to_dict(show_keys=["title"])

        assert_equals(
            ["title"],
            b_dict.keys()
        )
        b_dict2 = b.to_dict(show_keys=["pmid", "mesh_terms"])

        assert_equals(
            ["pmid", "mesh_terms"],
            b_dict2.keys()
        )
        assert_equals(
            '18767901',
            b_dict2["pmid"]
        )


    def test_pub_dates(self):
        test_tuples = [
            ("2008 Sep 30", "2008-09-30"),
            ("2008 Sep 1", "2008-09-01"),
            ("2008 Sep", "2008-09-01"),
            ("2008 Sep-Oct", "2008-09-01"),
            ("2008", "2008-01-01"),
            ("2008 Fall", "2008-10-01"),
        ]
        for (given, expected) in test_tuples:     
            biblio = Biblio({"pmid": "owner_pmid", "DP": given})
            # print biblio.pub_date[0:10], "for", given
            assert_equals(biblio.pub_date[0:10], expected)




