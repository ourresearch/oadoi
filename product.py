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

    @todo comment this back in when it stops being massively slow.
    http://discovery.ucl.ac.uk/1450592/
    None

    =http://eprints.gla.ac.uk/20877/
    =None

    This is the (actions required) one. not sure. might generate false negatives
    =http://nora.nerc.ac.uk/8783/
    =None
    """
    blacklist_phrases = [

        "full text not available",
        "full text not currently available",
        "no files associated with this item",
        "full-text and supplementary files are not available",

        # not sure about this one
        "(login required)"
        ""

    ]

    """
    if it's talking about how only admins can see it, it's not really open.

    =http://sro.sussex.ac.uk/54348/
    =None

    =http://researchbank.acu.edu.au/fea_pub/434/
    =None
    """
    blacklist_phrases += [
        "admin only"
    ]


    """
    let's find us some paywalls

    =http://www.cell.com/trends/genetics/abstract/S0168-9525(07)00023-6
    =None
    """
    blacklist_phrases.append("purchase access")


    for phrase in blacklist_phrases:
        if phrase in page_words:
            print u"found a blacklist phrase: ", phrase, url
            return None





    # admin_only_matches = re.findall(ur"download(.*?)admin only", page_words)
    # admin_only_matches += re.findall(ur"admin only(.*?)download", page_words)
    # if admin_only_matches:
    #     for m in admin_only_matches:
    #         if len(m.split()) <= 3:
    #             return None



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
        download text has the word "download" it is somewhere, and the link is pointing to a PDF file:

        =http://eprints.whiterose.ac.uk/77866/
        =http://eprints.whiterose.ac.uk/77866/25/ggge20346_with_coversheet.pdf

        note that researchgate can return various different things after the ? part of url.
        makes for fussy testing but shouldn't matter much in production
        =https://www.researchgate.net/publication/235915359_Promotion_of_Virtual_Research_Communities_in_CHAIN
        =https://www.researchgate.net/profile/Bruce_Becker4/publication/235915359_Promotion_of_Virtual_Research_Communities_in_CHAIN/links/0912f5141bd165b4ef000000.pdf?origin=publication_detail
        """
        if "download" in link_text:
            if len(re.findall(ur"\.pdf\b", link_target)):
                return link_target



        """
        download link anchor text is something like foobar.pdf

        =http://hdl.handle.net/1893/372
        =http://dspace.stir.ac.uk/bitstream/1893/372/1/Corley%20COGNITION%202007.pdf

        =https://research-repository.st-andrews.ac.uk/handle/10023/7421
        =https://research-repository.st-andrews.ac.uk/bitstream/handle/10023/7421/Manuscripts_edited_final.pdf?sequence=1&isAllowed=y

        probably superfluous:
        =https://hal.inria.fr/hal-00839984
        =https://hal.inria.fr/hal-00839984/document
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




