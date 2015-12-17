from time import time
from models.pypi_repo import save_all_repo_owners_and_key_committers
from app import db
import argparse
import logging
from util import elapsed
from time import time

from models.github_repo import add_python_repos_from_google_bucket
from models.github_repo import add_r_repos_from_google_bucket
from models.github_repo import add_github_about
from models.github_repo import add_all_github_about
from models.github_repo import add_github_dependency_lines
from models.github_repo import add_all_github_dependency_lines

from models.github_api import *
from models.github_repo import *
from models.person import *
from models.package import *
from models.pypi_package import *
from models.cran_package import *
from models.contribution import *
from jobs import *

def test_no_args():
    print "test_no_args function ran"

def test_one_arg(one):
    print "test_one_arg function ran", one

def test_one_optional_arg(one=None):
    print "test_one_optional_arg function ran", one

def test_two_args(one, two=None):
    print "test_two_args function ran", one, two


def main(fn, optional_args=None):

    start = time()

    # call function by its name in this module, with all args :)
    # http://stackoverflow.com/a/4605/596939
    if optional_args:
        globals()[fn](*optional_args)
    else:
        globals()[fn]()

    print "total time to run:", elapsed(start)



if __name__ == "__main__":



    # get args from the command line:
    parser = argparse.ArgumentParser(description="Run stuff.")
    parser.add_argument('function', type=str, help="what function you want to run")
    parser.add_argument('optional_args', nargs='*', help="positional args for the function")

    args = vars(parser.parse_args())

    function = args["function"]
    optional_args = args["optional_args"]

    print u"running main.py {function} with these args:{optional_args}\n".format(
        function=function, optional_args=optional_args)

    global logger
    logger = logging.getLogger("ti.main.{function}".format(
        function=function))

    main(function, optional_args)

    db.session.remove()


