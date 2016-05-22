from util import elapsed

import requests

from time import time
import inspect
import sys
import re
from lxml import html
from threading import Thread
import urlparse


def get_oa_url(url):
    r = requests.get(url, timeout=5)  # timeout in secs
    page = r.text

    page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
    tree = html.fromstring(page)

    page_words = " ".join(tree.xpath("//body")[0].text_content().lower().split())


    """
    if they're telling us there is no fulltext, let's quit there.

    =http://discovery.ucl.ac.uk/1450592/
    =None
    """
    if "full text not available" in page_words:
        print "found 'full text not available' for ", url
        return None



    links = tree.xpath("//a")
    for link in links:
        link_text = link.text_content().strip().lower()
        try:
            # we must use the RESOLVED url here, not the original one we came in with.
            # often there are one more redirects from that, and we need to use the final
            # one in order to build the absolute links.
            # conveniently, the final resolved URL is available from Requests as r.url:

            link_target = urlparse.urljoin(r.url, link.attrib["href"])
        except KeyError:
            # if the link doesn't point nowhere, it's no use to us
            continue

        """
        The download link doesn't have PDF at the end, but the download button is nice and clear.


        Here are some of Ethan's:
        =https://works.bepress.com/ethan_white/45/
        =https://works.bepress.com/ethan_white/45/download/

        =https://works.bepress.com/ethan_white/27/
        =None

        Here's from a DigitalCommons repo:
        =http://ro.uow.edu.au/aiimpapers/269/
        =http://ro.uow.edu.au/cgi/viewcontent.cgi?article=1268&context=aiimpapers
        """
        if link_text == "download":
            return link_target


        """
        download text is "download (54MB)":

        =http://eprints.whiterose.ac.uk/77866/
        =http://eprints.whiterose.ac.uk/77866/25/ggge20346_with_coversheet.pdf
        """
        if "download" in link_text:
            if link_target.endswith(".pdf"):
                return link_target


        """
        download link says something.pdf and links to a .pdf

        =http://hdl.handle.net/1893/372
        =http://dspace.stir.ac.uk/bitstream/1893/372/1/Corley%20COGNITION%202007.pdf
        """
        if re.search(ur".\.pdf\b", link_text):
            return link_target





    return None


def get_abs_url(base_url, input_url):
    if input_url.startswith("http"):
        return input_url
    else:
        pass


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
        "expected": expected_output,
        "passed": result == expected_output
    }




