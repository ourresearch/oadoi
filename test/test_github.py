import unittest
from test.utils import http
from test.utils import open_file_from_data_dir
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
from nose.tools import assert_items_equal

import json

from providers import github

handle = open_file_from_data_dir("github_users_jasonpriem.json")
github_user_json = json.loads(handle.read())


class TestGithub(unittest.TestCase):

    @http 
    def test_get_user_live_from_github(self):
        github_user_dict = github.get_repo_names("jasonpriem")
        repo_names = [u'5uni-Twitter-study', u'altmetrics-crawler', u'altmetrics-tools-iConference-poster', u'angular-seo-heroku', u'annotateit', u'annotator', u'bibserver', u'BlackBoard_awesome_patch', u'bootstrap', u'daphne-masters-paper', u'FeedVis', u'HumanNameParser.php', u'ICanHaz.js', u'negotiate', u'php-backtype', u'plain-jane', u'plos_altmetrics_study', u'rerankit', u'rImpactStory', u'schol-search-study', u'sils-annotate', u'zotero-report-cleaner']
        assert_equals(github_user_dict, repo_names)


    # def test_got_username(self):
    #     assert_equals(github_user_json, "hi")


