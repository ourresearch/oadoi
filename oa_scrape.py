from threading import Thread
import inspect
import sys
import os
import requests
import re
import urlparse
from time import time
from lxml import html
from lxml import etree
from contextlib import closing

from oa_local import find_normalized_license
from util import is_doi_url
from util import elapsed


def get_tree(page):
    page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
    try:
        tree = html.fromstring(page)
    except etree.XMLSyntaxError:
        print u"XMLSyntaxError in get_tree; not parsing."
        tree = None

    return tree


def scrape_for_fulltext_link(url):
    print u"getting URL: {}".format(url)

    license = "unknown"
    is_journal = is_doi_url(url) or (u"/doi/" in url)

    if u"ncbi.nlm.nih.gov" in url:
        print u"not scraping {} because is on our do not scrape list.".format(url)
        if "ncbi.nlm.nih.gov/pmc/articles/PMC" in url:
            # pmc has fulltext
            return (url, license)
        else:
            # is an nlm page but not a pmc page, so is not full text
            return (None, license)


    # print u"in scrape_for_fulltext_link"

    user_agent = {'User-Agent': 'oadoi.org'}
    with closing(requests.get(url, headers=user_agent, stream=True, timeout=10, verify=False)) as r:
        # if our url redirects to a pdf, we're done.
        # = open repo http://hdl.handle.net/2060/20140010374
        if resp_is_pdf(r):
            print u"the head says this is a PDF. success! [{}]".format(url)
            return (url, license)

        # get the HTML tree
        page = r.content
        license = find_normalized_license(page)
        if license != "unknown":
            # = open 10.1136/bmj.i2716 cc-by
            # = open 10.1136/bmj.i1209 cc-by-nc
            # print "FOUND A LICENSE!", license, url
            return (url, license)

        # if they are linking to a .docx or similar, this is open.
        # this only works for repos... a ".doc" in a journal is not the article. example:
        # = closed journal http://doi.org/10.1007/s10822-012-9571-0
        if not is_journal:
            doc_link = find_doc_download_link(page)
            if doc_link is not None:
                # print u"found a .doc download link {} [{}]".format(
                #     get_link_target(doc_link, r.url), url)
                return (url, license)

        pdf_download_link = find_pdf_link(page, url)
        if pdf_download_link is not None:
            # print u"found a PDF download link: {} {} [{}]".format(
            #     pdf_download_link.href, pdf_download_link.anchor, url)

            pdf_url = get_link_target(pdf_download_link, r.url)
            if is_journal:
                # print u"this is a journal. checking to see the PDF link actually gets a PDF [{}]".format(url)
                # if they are linking to a PDF, we need to follow the link to make sure it's legit
                if gets_a_pdf(pdf_download_link, r.url):
                    return (pdf_url, license)
            else:
                return (pdf_url, license)

    # print u"found no PDF download link [{}]".format(url)
    return (None, license)


# = open journal http://www.emeraldinsight.com/doi/full/10.1108/00251740510597707
# = closed journal http://www.emeraldinsight.com/doi/abs/10.1108/14777261111143545


def gets_a_pdf(link, base_url):

    if is_purchase_link(link):
        return False

    absolute_url = get_link_target(link, base_url)
    start = time()
    try:
        user_agent = {'User-Agent': 'oadoi.org'}
        with closing(requests.get(absolute_url, header=user_agent, stream=True, timeout=10, verify=False)) as r:
            if resp_is_pdf(r):
                print u"http header says this is a PDF. took {}s [{}]".format(
                    elapsed(start), absolute_url)
                return True

            # some publishers send a pdf back wrapped in an HTML page using frames.
            # this is where we detect that, using each publisher's idiosyncratic templates.
            # we only check based on a whitelist of publishers, because downloading this whole
            # page (r.content) is expensive to do for everyone.
            if 'onlinelibrary.wiley.com' in absolute_url:
                # = closed journal http://doi.org/10.1111/ele.12585
                # = open journal http://doi.org/10.1111/ele.12587 cc-by
                if '<iframe' in r.content:
                    print u"this is a Wiley 'enhanced PDF' page. took {}s [{}]".format(
                        elapsed(start), absolute_url)
                    return True

            elif 'ieeexplore' in absolute_url:
                # (this is a good example of one dissem.in misses)
                # = open journal http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6740844
                # = closed journal http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6045214
                if '<frame' in r.content:
                    print u"this is a IEEE 'enhanced PDF' page. took {}s [{}]".format(
                                elapsed(start), absolute_url)
                    return True


        # print u"we've decided this ain't a PDF. took {}s [{}]".format(
        #     elapsed(start), absolute_url)
        return False
    except requests.exceptions.ConnectionError:
        print u"ERROR: connection error in gets_a_pdf, skipping."
        return False
    except requests.Timeout:
        print u"ERROR: timeout error in gets_a_pdf, skipping."
        return False



def find_doc_download_link(page):
    tree = get_tree(page)
    for link in get_useful_links(tree):
        # there are some links that are FOR SURE not the download for this article
        if has_bad_anchor_word(link.anchor):
            continue

        # = open repo https://lirias.kuleuven.be/handle/123456789/372010
        if ".doc" in link.href or ".doc" in link.anchor:
            return link

    return None


def resp_is_pdf(resp):
    for k, v in resp.headers.iteritems():
        key = k.lower()
        val = v.lower()

        if key == "content-type" and "application/pdf" in val:
            return True

        if key =='content-disposition' and "pdf" in val:
            return True

    return False


class DuckLink(object):
    def __init__(self, href, anchor):
        self.href = href
        self.anchor = anchor


def get_useful_links(tree):
    ret = []
    if tree is None:
        return ret

    links = tree.xpath("//a")

    for link in links:
        link_text = link.text_content().strip().lower()
        if not link_text:
            continue
        else:
            link.anchor = link_text

        if "href" not in link.attrib:
            continue
        else:
            link.href = link.attrib["href"]

        ret.append(link)

    return ret


def is_purchase_link(link):
    # = closed journal http://www.sciencedirect.com/science/article/pii/S0147651300920050
    if "purchase" in link.anchor:
        print u"found a purchase link!", link.anchor, link.href
        return True

    return False

def has_bad_anchor_word(anchor_text):
    anchor_blacklist = [
        # = closed repo https://works.bepress.com/ethan_white/27/
        "user",
        "guide",

        # = closed 10.1038/ncb3399
        "checklist",

        # = closed http://europepmc.org/abstract/med/18998885
        "bulk downloads",

        # no examples for these yet
        "supplement",
        "figure",
        "faq"
    ]
    for bad_word in anchor_blacklist:
        if bad_word in anchor_text:
            return True

    return False


# url just used for debugging
def find_pdf_link(page, url):

    # tests we are not sure we want to run yet:
    # if it has some semantic stuff in html head that says where the pdf is: that's the pdf.
    # = open http://onlinelibrary.wiley.com/doi/10.1111/tpj.12616/abstract





    # DON'T DO THESE THINGS:
    # search for links with an href that has "pdf" in it because it breaks this:
    # = closed journal http://onlinelibrary.wiley.com/doi/10.1162/10881980152830079/abstract




    tree = get_tree(page)
    if tree is None:
        return None

    # before looking in links, look in meta for the pdf link
    # = open journal http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/abstract
    # = open journal http://doi.org/10.1002/meet.2011.14504801327
    # = open repo http://hdl.handle.net/10088/17542
    # = open http://handle.unsw.edu.au/1959.4/unsworks_38708 cc-by

    if "citation_pdf_url" in page:
        metas = tree.xpath("//meta")
        for meta in metas:
            if "name" in meta.attrib and meta.attrib["name"]=="citation_pdf_url":
                if "content" in meta.attrib:
                    link = DuckLink(href=meta.attrib["content"], anchor="<meta citation_pdf_url>")
                    return link

    # (this is a good example of one dissem.in misses)
    # = open journal http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6740844
    # = closed journal http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6045214
    if '"isOpenAccess":true' in page:
        # this is the free fulltext link
        article_number = url.rsplit("=", 1)[1]
        href = "http://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber={}".format(article_number)
        link = DuckLink(href=href, anchor="<ieee isOpenAccess>")
        return link


    for link in get_useful_links(tree):

        # there are some links that are SURELY NOT the pdf for this article
        if has_bad_anchor_word(link.anchor):
            continue



        # download link ANCHOR text is something like "manuscript.pdf" or like "PDF (1 MB)"
        # = open repo http://hdl.handle.net/1893/372
        # = open repo https://research-repository.st-andrews.ac.uk/handle/10023/7421
        # = open repo http://dro.dur.ac.uk/1241/
        if "pdf" in link.anchor:
            return link


        # button says download
        # = open repo https://works.bepress.com/ethan_white/45/
        # = open repo http://ro.uow.edu.au/aiimpapers/269/
        # = open repo http://eprints.whiterose.ac.uk/77866/
        if "download" in link.anchor:
            if "citation" in link.anchor:
                pass
            else:
                return link

        # download link is identified with an image
        for img in link.findall("img"):
            try:
                if "pdf" in img.attrib["src"].lower():
                    return link
            except KeyError:
                pass  # no src attr

        try:
            if "pdf" in link.attrib["title"].lower():
                return link
        except KeyError:
            pass



    return None



def get_link_target(link, base_url):
    try:
        url = link.href
    except KeyError:
        return None

    url = re.sub(ur";jsessionid=\w+", "", url)
    if base_url:
        url = urlparse.urljoin(base_url, url)

    return url



# tell base about these
# is open at PMC.  BASE says is open but gives only a closed access url.
# so we are going to say it is closed from a scraping perspective.
# = closed 10.1038/nature16932



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
        (self.fulltext_url, self.license_result) = scrape_for_fulltext_link(self.url)
        if self.fulltext_url != None:
            self.open_result = True

        self.elapsed = elapsed(my_start)


    @property
    def passed(self):
        if not self.open_expected:
            print self.url
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
            for arg in arg_list:
                if arg.startswith("http"):
                    my_test_case.url = arg
                elif arg.startswith("10."):
                    my_test_case.url = u"http://doi.org/{}".format(arg)

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
