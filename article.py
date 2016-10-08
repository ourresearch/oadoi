from util import elapsed

import requests

from time import time
from contextlib import closing
import inspect
import sys
import re
from lxml import html
from lxml import etree
from threading import Thread
import urlparse
import logging

class Article(object):
    def __init__(self, url, host=None):
        self.url = url
        self.host = host
        self.error = None
        self.error_message = None
        self.is_oa = None
        self.license = None


    def set_is_oa_and_license(self, set_license_even_if_not_oa=False):
        try:
            self.is_oa = is_oa(self.url, self.host)
            if self.is_oa or set_license_even_if_not_oa:
                self.license = scrape_license(self.url)
        except requests.Timeout, e:
            self.error = "timeout"
            self.error_message = unicode(e.message).encode("utf-8")
        except requests.exceptions.ConnectionError, e:
            self.error = "connection"
            self.error_message = unicode(e.message).encode("utf-8")
        except requests.exceptions.RequestException, e:
            self.error = "other requests error"
            self.error_message = unicode(e.message).encode("utf-8")
        except etree.XMLSyntaxError, e:
            self.error = "xml"
            self.error_message = unicode(e.message).encode("utf-8")
        except Exception, e:
            logging.exception(u"exception in is_oa")
            self.error = "other"
            self.error_message = unicode(e.message).encode("utf-8")

    def to_dict(self):
        response = {
            "url": self.url,
            "is_oa": self.is_oa,
            "license": self.license,
            "host": self.host,
        }
        if self.error:
            response["error"] = self.error
            response["error_message"] = self.error_message
        return response


def get_oa_in_parallel(article_tuples, set_license_even_if_not_oa=False):
    articles = []
    for (url, host) in article_tuples:
        articles.append(Article(url, host))

    threads = []
    for my_article in articles:
        process = Thread(target=my_article.set_is_oa_and_license, args=[set_license_even_if_not_oa])
        process.start()
        threads.append(process)

    # wait till all work is done
    for process in threads:
        process.join(timeout=5)

    return articles



def get_tree(page):
    page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
    tree = html.fromstring(page)
    return tree




# from Impactstory
def find_normalized_license(text):
    normalized_text = text.replace(" ", "").replace("-", "").lower()
    # print normalized_text

    # the lookup order matters
    # assumes no spaces, no dashes, and all lowercase
    # inspired by https://github.com/CottageLabs/blackbox/blob/fc13e5855bd13137cf1ef8f5e93883234fdab464/service/licences.py
    # thanks CottageLabs!  :)

    license_lookups = [
        ("creativecommons.org/licenses/byncnd", "cc-by-nc-nd"),
        ("creativecommonsattributionnoncommercialnoderiv", "cc-by-nc-nd"),
        ("ccbyncnd", "cc-by-nc-nd"),

        ("creativecommons.org/licenses/byncsa", "cc-by-nc-sa"),
        ("creativecommonsattributionnoncommercialsharealike", "cc-by-nc-sa"),
        ("ccbyncsa", "cc-by-nc-sa"),

        ("creativecommons.org/licenses/bynd", "cc-by-nd"),
        ("creativecommonsattributionnoderiv", "cc-by-nd"),
        ("ccbynd", "cc-by-nd"),

        ("creativecommons.org/licenses/bysa", "cc-by-sa"),
        ("creativecommonsattributionsharealike", "cc-by-sa"),
        ("ccbysa", "cc-by-sa"),

        ("creativecommons.org/licenses/bync", "cc-by-nc"),
        ("creativecommonsattributionnoncommercial", "cc-by-nc"),
        ("ccbync", "cc-by-nc"),

        ("creativecommons.org/licenses/by", "cc-by"),
        ("creativecommonsattribution", "cc-by"),
        ("ccby", "cc-by"),

        ("creativecommons.org/publicdomain/zero", "cc0"),
        ("creativecommonszero", "cc0"),
        ("cc0", "cc0"),

        ("publicdomain", "pd")

        # removing this one from this usecase, because often hits on sidebar instructions about
        # how to make things OA, rather than on the article itself being oa
        # ("openaccess", "oa")
    ]

    for (lookup, license) in license_lookups:
        if lookup in normalized_text:
            return license
    return "unknown"


def scrape_license(url):
    # print u"in scrape_license, getting URL: {}".format(url)

    with closing(requests.get(url, stream=True, timeout=100, verify=False)) as r:
        # get the HTML tree
        page = r.content
        license = find_normalized_license(page)
        return license



def is_oa(url, host):
    # print u"getting URL: {}".format(url)


    with closing(requests.get(url, stream=True, timeout=100, verify=False)) as r:
        # if our url redirects to a pdf, we're done.
        # = open repo http://hdl.handle.net/2060/20140010374
        if resp_is_pdf(r):
            print u"the head says this is a PDF. we're quitting. [{}]".format(url)
            return True

        # get the HTML tree
        page = r.content

        # if they are linking to a .docx or similar, this is open.
        # this only works for repos... a ".doc" in a journal is not the article. example:
        # = closed journal http://link.springer.com/article/10.1007%2Fs10822-012-9571-0
        if host == "repo":
            doc_link = find_doc_download_link(page)
            if doc_link is not None:
                print u"found a .doc download link {} [{}]".format(
                    get_link_target(doc_link, r.url), url)
                return True

        pdf_download_link = find_pdf_link(page, url)
        if pdf_download_link is not None:
            print u"found a PDF download link: {} {} [{}]".format(
                pdf_download_link.href, pdf_download_link.anchor, url)

            if host == "journal":
                # print u"this is a journal. checking to see the PDF link actually gets a PDF [{}]".format(url)
                # if they are linking to a PDF, we need to follow the link to make sure it's legit
                return gets_a_pdf(pdf_download_link, r.url)

            else:  # host is "repo"
                return True

        # print u"found no PDF download link [{}]".format(url)
        return False


# = open journal http://www.emeraldinsight.com/doi/full/10.1108/00251740510597707
# = closed journal http://www.emeraldinsight.com/doi/abs/10.1108/14777261111143545


def gets_a_pdf(link, base_url):
    if is_purchase_link(link):
        return False

    absolute_url = get_link_target(link, base_url)
    start = time()
    with closing(requests.get(absolute_url, stream=True, timeout=5, verify=False)) as r:
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
            # = open journal http://doi.org/10.1111/ele.12587
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


        print u"we've decided this ain't a PDF. took {}s [{}]".format(
            elapsed(start), absolute_url)
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

    # before looking in links, look in meta for the pdf link
    # = open journal http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/abstract
    # = open journal http://doi.org/10.1002/meet.2011.14504801327
    # = open repo http://hdl.handle.net/10088/17542

    if "citation_pdf_url" in page:
        metas = tree.xpath("//meta")
        for meta in metas:
            if "name" in meta.attrib and meta.attrib["name"]=="citation_pdf_url":
                if "content" in meta.attrib:
                    link = DuckLink(href=meta.attrib["content"], anchor="<meta citation_pdf_url>")
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

        # = closed journal http://www.sciencedirect.com/science/article/pii/S0147651300920050
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
    def __init__(self, oa_expected=False, host="repo", url=None):
        self.expected = oa_expected
        self.host = host
        self.url = url

        self.elapsed = None
        self.result = None

    def run(self):
        my_start = time()
        self.result = is_oa(self.url, self.host)
        self.elapsed = elapsed(my_start)

    @property
    def passed(self):
        return self.expected == self.result

    @property
    def display_result(self):
        return self._display_open_or_closed(self.result)

    @property
    def display_expected(self):
        return self._display_open_or_closed(self.expected)

    def _display_open_or_closed(self, is_open):
        if is_open:
            return "open"
        else:
            return "closed"



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


        # immediately quit and return this one if the "only" flag is set
        if "only" in arg_list:
            return [my_test_case]

        # otherwise put this in the list and keep iterating
        else:
            ret.append(my_test_case)

    return ret



def run_test(test_case):
    test_case.run()




