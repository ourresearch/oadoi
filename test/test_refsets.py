import unittest
from nose.tools import nottest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
from nose.tools import assert_items_equal


from test.utils import setup_redis_for_unittests

class TestRefsets(unittest.TestCase):

    def setUp(self):
        self.r = setup_redis_for_unittests()

    def test_from_url(self):
        self.r.set("test", "foo")
        assert_equals(self.r.get("test"), "foo")
