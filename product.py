from util import elapsed

import requests

from time import time
from contextlib import closing
import inspect
import sys
import re
from lxml import html
from threading import Thread
import urlparse



def is_oa(url, host, verbose=False):
    if verbose:
        print "getting URL: ", url

    with closing(requests.get(url, stream=True, timeout=100)) as r:
        # if our url redirects to a pdf, we're done.
        # = open repo http://hdl.handle.net/2060/20140010374
        if head_says_pdf(r):
            if verbose:
                print "the head says this is a PDF. we're quitting.", url
            return True

        # get the HTML tree and the bucket of words
        page = r.text
        page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
        start_parsing = time()
        tree = html.fromstring(page)
        if verbose:
            print "parsing the html tree took {} for {}".format(elapsed(start_parsing), url)


        useful_links = get_useful_links(tree)
        try:
            page_words = " ".join(tree.xpath("//body")[0].text_content().lower().split())
        except IndexError:
            # there is no body tag
            page_words = ""





        # tests that use the bucket of words

        # reasons to reject outright
        if page_says_closed(page_words, host, verbose):
            return False

        # if the page says open access on it, we just say that's the OA URL because it saves tons of time.
        # this doesn't work for repos because they like to advertise about the benefits of
        # open access elsewhere on the page.
        # = open journal http://doi.org/10.1039/c5sm02502h
        # @todo get rid of this, it does't work.


        if host == "journal" and "open access" in page_words:
            if verbose:
                print "found phrase 'open access' on this page: ", url

            return True






        # tests that use the HTML tree

        # if they are linking to a .docx or similar, this is probably open.
        doc_link = find_doc_download_link(tree, verbose)
        if doc_link is not None:
            if verbose :
                print "found OA link target (non-pdf): ", get_link_target(doc_link, r.url)
            return True


        # if a journal is linking to an open license, it's an open article
        # = open journal http://doi.org/10.17528/cifor/004490
        if host == "journal":
            for link in useful_links:
                if "creativecommons.org/licenses/" in link["href"]:
                    if verbose:
                        print "Founds a CC-license for this journal article", link["anchor"]
                    return True



        # if they are linking to a PDF, we need to follow the link to make sure it's legit
        pdf_download_link = find_pdf_link(tree, verbose)

        if pdf_download_link is not None:
            target = get_link_target(pdf_download_link, r.url)
            if verbose:
                print "found OA link target: ", target, host

            # =  open journal http://www.emeraldinsight.com/doi/full/10.1108/00251740510597707
            # = closed journal http://www.emeraldinsight.com/doi/abs/10.1108/14777261111143545
            if host == "journal":
                if verbose:
                    print "this is a journal. checking to see the PDF link actually gets a PDF"
                return gets_a_pdf(target, verbose=verbose)
            else:
                return True

        return False



def gets_a_pdf(url, verbose=False):
    start = time()
    with closing(requests.get(url, stream=True, timeout=5)) as r:
        if head_says_pdf(r):
            if verbose:
                print "http header says this is a PDF. took {}s".format(elapsed(start))
                print r.headers
            return True
        else:
            if verbose:
                print "the http header says this ain't a PDF. took {}s".format(elapsed(start))
            return False

def find_doc_download_link(tree, verbose=False):

    # the top of this loop is copied from find_pdf_link()
    links = tree.xpath("//a")
    for link in links:
        link_text = link.text_content().strip().lower()
        # if verbose:
        #     print "trying with link text: ", link_text

        try:
            link_target = link.attrib["href"]
        except KeyError:
            # if the link doesn't point nowhere, it's no use to us
            continue


        # everything below is unique to this function.

        # = open repo https://lirias.kuleuven.be/handle/123456789/372010
        if ".docx" in link_target:
            return link

    return None


def head_says_pdf(resp):
    for k, v in resp.headers.iteritems():
        key = k.lower()
        val = v.lower()

        if key == "content-type" and "application/pdf" in val:
            return True

        if key =='content-disposition' and "pdf" in val:
            return True

    return False


def get_useful_links(tree):
    ret = []
    links = tree.xpath("//a")

    for link in links:
        link_text = link.text_content().strip().lower()
        try:
            link_target = link.attrib["href"]
        except KeyError:
            continue

        ret.append({
            "anchor": link_text,
            "href": link_target,
            "elem": link
        })

    return ret


def find_pdf_link(tree, verbose=False):
    links = tree.xpath("//a")
    for link in links:
        link_text = link.text_content().strip().lower()
        if verbose:
            print "trying with link text: ", link_text

        try:
            link_target = link.attrib["href"]
        except KeyError:
            # if the link doesn't point nowhere, it's no use to us
            if verbose:
                print "this link doesn't point anywhere. abandoning it."

            continue






        """
        The download link doesn't have PDF at the end, but the download button is nice and clear.

        = open repo https://works.bepress.com/ethan_white/45/

        = closed repo https://works.bepress.com/ethan_white/27/

        = open repo http://ro.uow.edu.au/aiimpapers/269/
        """
        if link_text == "download":
            return link


        """
        download text has the word "download" it is somewhere. This is in a seperate
        block right now because we may need more precision on it (eg check the link_target for .pfd)

        = open repo http://eprints.whiterose.ac.uk/77866/

        note that researchgate can return various different things after the ? part of url.
        makes for fussy testing but shouldn't matter much in production
        = open repo https://www.researchgate.net/publication/235915359_Promotion_of_Virtual_Research_Communities_in_CHAIN
        """
        if "download" in link_text:
            return link



        """
        download link anchor text is something like foobar.pdf

        = open repo http://hdl.handle.net/1893/372

        = open repo https://research-repository.st-andrews.ac.uk/handle/10023/7421
        """
        if len(re.findall(ur".\.pdf\b", link_text)):
            return link


        """
        the link anchor text is just "PDF"

        = open repo http://dro.dur.ac.uk/1241/
        """
        if link_text.lower() == "pdf":
            return link



        """
        download link is identified with an image

        = open repo http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.587.8827
        """
        for img in link.findall("img"):
            try:
                if "pdf" in img.attrib["src"].lower():
                    return link
            except KeyError:
                continue  # no src attr

    return None


def url_leads_to_pdf(url):
    pass

def page_says_closed(page_words, host, verbose=False):

    if host == "journal":
        blacklist_phrases = [
            # = closed journal http://www.cell.com/trends/genetics/abstract/S0168-9525(07)00023-6
            "purchase access"
        ]
    elif host == "repo":
        blacklist_phrases = [

            # = closed repo https://lirias.kuleuven.be/handle/123456789/9821
            "request a copy",

            # = closed repo http://eprints.gla.ac.uk/20877/

            "file restricted",
            "full text not available",
            "full text not currently available",
            "full-text and supplementary files are not available",
            "no files associated with this item",
            "restricted to registered users",
            "does not currently have the full-text",
            "does not currently have full-text",
            "does not have the full-text",
            "does not have full-text",

            # not sure if we should keep this one, danger of false negs
            # = closed repo http://nora.nerc.ac.uk/8783/
            "(login required)",

            # = closed repo http://sro.sussex.ac.uk/54348/
            # = closed repo http://researchbank.acu.edu.au/fea_pub/434/
            "admin only"
        ]

    for phrase in blacklist_phrases:
        if phrase in page_words:
            if verbose:
                print "{} is closed! We found the phrase '{}'".format(host, phrase)
            return True

    return False





def is_pdf_url(url):
    return len(re.findall(ur"\.pdf\b", url)) > 0

def get_link_target(link_elem, base_url):
    try:
        url = link_elem.attrib["href"]
    except KeyError:
        return None

    url = re.sub(ur";jsessionid=\w+", "", url)
    if base_url:
        url = urlparse.urljoin(base_url, url)

    return url


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
    def __init__(self, oa_expected=False, host="repo", url=None, verbose=False):
        self.expected = oa_expected
        self.host = host
        self.url = url
        self.verbose = verbose

        self.elapsed = None
        self.result = None

    def run(self):
        my_start = time()
        self.result = is_oa(self.url, self.host, self.verbose)
        self.elapsed = elapsed(my_start)

    @property
    def passed(self):
        return self.expected == self.result



def get_test_cases():
    ret = []

    # get all the test pairs
    this_module = sys.modules[__name__]
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
            my_test_case.expected = True

        if "journal" in arg_list:
            my_test_case.host = "journal"

        if "verbose" in arg_list:
            my_test_case.verbose = True

        # immediately quit and return this one if the "only" flag is set
        if "only" in arg_list:
            my_test_case.verbose = True
            return [my_test_case]

        # otherwise put this in the list and keep iterating
        else:
            ret.append(my_test_case)

    return ret



def run_test(test_case):
    test_case.run()




