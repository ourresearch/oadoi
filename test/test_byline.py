from models.byline import Byline
from models.person import Person

import unittest
from nose.tools import assert_equals
from nose.tools import assert_not_equals
from nose.tools import assert_true
from nose.tools import assert_items_equal


class TestByline(unittest.TestCase):

    test_bylines = """David Bronaugh <bronaugh@uvic.ca>, Arelia Werner <wernera@uvic.ca> for the Pacific Climate Impacts Consortium
        Keon-Woong Moon [aut, cre]
        Corentin M Barbu [aut, cre],<U+000a>Sebastian Gibb [ctb]
        Philippe Grosjean [aut, cre],
        Kevin Denis [aut]
        Erik Otarola-Castillo, Jesse Wolfhagen, Max D. Price
        Achim Zeileis [aut, cre],<U+000a>Gabor Grothendieck [aut],<U+000a>Jeffrey A. Ryan [aut],<U+000a>Felix Andrews [ctb]
        David Beiner
        Fang Liu <fang.liu.131@nd.edu> with contributions from Yunchuan Kong <ykong@cuhk.edu.hk>
        Jonathan M. Lees <jonathan.lees@unc.edu>
        Stefan Evert <stefan.evert@uos.de>, Marco Baroni<U+000a><marco.baroni@unitn.it>
        """.split("\n")

    def test_clean_byline_string(self):
        byline = Byline(self.test_bylines[2])
        expected = '        Corentin M Barbu [aut, cre], Sebastian Gibb [ctb]'
        assert_equals(byline._clean_byline(), expected)

    def test_author_email_pairs(self):
        for byline_string in self.test_bylines:
            byline = Byline(byline_string)
            print "\n{}\n{}\n".format(byline.author_email_pairs(), byline_string)
        # assert_equals(byline.author_email_pairs(), "hi")        

    def test_author_halt(self):
        test_string = """Fortran code by H. Akima<U+000a>R port by Albrecht Gebhardt <albrecht.gebhardt@uni-klu.ac.at><U+000a>aspline function by Thomas Petzoldt <thomas.petzoldt@tu-dresden.de><U+000a>interp2xyz, enhancements and corrections by Martin Maechler <maechler@stat.math.ethz.ch>"""
        byline = Byline(test_string)
        response = byline.author_email_pairs()
        expected = None
        assert_equals(response, expected)

    def test_author_square_brackets(self):
        test_string = """Jie (Kate) Hu [aut, cre],
            Norman Breslow [aut],
            Gary Chan [aut]"""
        byline = Byline(test_string)
        response = byline.author_email_pairs()
        expected = None
        assert_equals(response, expected)


