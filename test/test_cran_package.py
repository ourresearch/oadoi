from models import cran_package
from test.utils import http

import unittest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
from nose.tools import assert_items_equal


class TestCranPackage(unittest.TestCase):
	pass
	# @http
 #    def test_get_tags(self):
 #        response = cran_package.get_tags("knitr")
 #        expected = ['ReproducibleResearch']
 #        assert_equals(response, expected)

 #        response = cran_package.get_tags("MASS")
 #        expected = ['Distributions', 'Econometrics', 'Environmetrics', 'Multivariate', 'NumericalMathematics', 'Pharmacokinetics', 'Psychometrics', 'Robust', 'SocialSciences']
 #        assert_equals(response, expected)


