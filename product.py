from util import elapsed

import requests

from time import time
import inspect
import sys
import re
from threading import Thread


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
        self.elapsed = 0


    def run(self):
        start = time()
        
        # get all the test pairs
        this_module = sys.modules[__name__]
        file_source = inspect.getsource(this_module)
        p = re.compile(ur'^\s+=(.+)\n\s+=(.+)', re.MULTILINE)
        test_pairs = re.findall(p, file_source)
        
        # start a thread for each test pair,
        # and save the results in a single shared list, test_results
        threads = []
        test_results = []
        for url, expected_output in test_pairs:
            process = Thread(target=test_url_for_threading, args=[url, expected_output, test_results])
            process.start()
            threads.append(process)
    
        # wait till all work is done
        for process in threads:
            process.join()

        # store the test results
        self.results = test_results
        self.elapsed = elapsed(start)


def test_url_for_threading(url, expected_output, all_test_results):
    res = test_url(url, expected_output)
    all_test_results.append(res)
    return all_test_results

def test_url(url, expected_output):

    if expected_output == "None":
        expected_output = None

    my_start = time()
    result = get_oa_url(url)

    return {
        "elapsed": elapsed(my_start),
        "url": url,
        "result": result,
        "passed": result == expected_output
    }




