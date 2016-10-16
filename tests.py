from time import time
from util import elapsed
from threading import Thread
from contextlib import closing
import inspect
import sys
import re
import os
import oa_scrape

class Tests(object):
    def __init__(self):
        self.passed = []
        self.elapsed = 0
        self.results = []

    def run(self):
        start = time()

        test_cases = get_test_cases()
        threads = []
        for case in test_cases:
            process = Thread(target=run_test, args=[case])
            process.start()
            threads.append(process)

        # wait till all work is done
        for process in threads:
            process.join(timeout=5)

        # store the test results
        self.results = test_cases
        self.elapsed = elapsed(start)



class TestCase(object):
    def __init__(self, open_expected=False, license_expected=None, url=None):
        self.open_expected = open_expected
        self.license_expected = license_expected
        self.url = url
        self.fulltext_url = None

        self.open_result = False
        self.license_expected = "unknown"

        self.elapsed = None


    def run(self):
        my_start = time()
        (self.fulltext_url, self.license_result) = oa_scrape.scrape_for_fulltext_link(self.url)
        if self.fulltext_url != None:
            self.open_result = True

        self.elapsed = elapsed(my_start)


    @property
    def passed(self):
        return (self.open_expected == self.open_result) and (self.license_expected == self.license_result)

    @property
    def display_result(self):
        return self._display_open_or_closed(self.open_result, self.license_result)

    @property
    def display_expected(self):
        return self._display_open_or_closed(self.open_expected, self.license_expected)

    def _display_open_or_closed(self, is_open, license=None):
        if is_open:
            open_string = "open"
        else:
            open_string = "closed"

        if not license:
            license = ""

        return u"{} {}".format(open_string, license)



def get_test_cases():
    ret = []

    # get all the test pairs
    for module_name in ["oa_scrape"]:

        this_module = sys.modules[module_name]
        file_source = inspect.getsource(this_module)
        p = re.compile(ur'^[\s#]*=(.+)', re.MULTILINE)
        test_lines = re.findall(p, file_source)

        for line in test_lines:
            my_test_case = TestCase()
            arg_list = line.split()

            # get the required URL
            my_test_case.url = [arg for arg in arg_list if arg.startswith("http")][0]

            # get optional things (optional because there are defaults set already)
            if "open" in arg_list:
                my_test_case.open_expected = True

            for arg in arg_list:
                if arg.startswith("cc-") or arg=="pd":
                    my_test_case.license_expected = arg

            # immediately quit and return this one if the "only" flag is set
            if "only" in arg_list:
                return [my_test_case]

            # otherwise put this in the list and keep iterating
            else:
                ret.append(my_test_case)

    return ret



def run_test(test_case):
    test_case.run()



