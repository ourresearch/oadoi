from util import elapsed

import requests

from time import time
import inspect
import sys
import re


def get_oa_url(url):
    r = requests.get(url)
    page = r.text

    """
    first test, on SelectedWorks site for ethan:

    =https://works.bepress.com/ethan_white/45/
    =https://works.bepress.com/ethan_white/45/download/

    =https://works.bepress.com/ethan_white/27/
    =None
    """
    return None




class Tests(object):
    def __init__(self):
        self.passed = []
        self.failed = []
        self.count = 0
        self.elapsed = 0


    def run(self):
        start = time()
        this_module = sys.modules[__name__]
        file_source = inspect.getsource(this_module)

        p = re.compile(ur'^\s+=(.+)\n\s+=(.+)', re.MULTILINE)
        test_pairs = re.findall(p, file_source)

        for url, expected_result in test_pairs:
            test_result = test_url(url, expected_result)

            if test_result["passed"]:
                self.passed.append(test_result)
            else:
                self.failed.append(test_result)

        self.count = len(self.passed) + len(self.failed)
        self.elapsed = elapsed(start)



def test_url(url, expected_result):

    if expected_result == "None":
        expected_result = None

    my_start = time()
    result = get_oa_url(url)

    return {
        "elapsed": elapsed(my_start),
        "url": url,
        "result": result,
        "passed": result == expected_result
    }




