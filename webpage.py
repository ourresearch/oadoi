 #!/usr/bin/python
 # -*- coding: utf-8 -*-

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
from open_version import OpenVersion
from http_cache import http_get
from util import is_doi_url
from util import elapsed
from http_cache import is_response_too_large


DEBUG_SCRAPING = False



class Webpage(object):
    def __init__(self, **kwargs):
        self.url = None
        self.scraped_pdf_url = None
        self.scraped_open_metadata_url = None
        self.scraped_license = "unknown"
        self.error = None
        self.error_message = None
        self.related_pub = None
        for (k, v) in kwargs.iteritems():
            self.__setattr__(k, v)
        if not self.url:
            self.url = u"http://doi.org/{}".format(self.doi)

    @property
    def doi(self):
        if self.related_pub:
            return self.related_pub.doi
        return None

    @property
    def fulltext_url(self):
        if self.scraped_pdf_url:
            return self.scraped_pdf_url
        if self.scraped_open_metadata_url:
            return self.scraped_open_metadata_url
        return None

    @property
    def has_fulltext_url(self):
        if self.scraped_pdf_url or self.scraped_open_metadata_url:
            return True
        return False


    #overridden in some subclasses
    @property
    def is_open(self):
        if self.scraped_pdf_url or self.scraped_open_metadata_url:
            return True
        if self.scraped_license and self.scraped_license != "unknown":
            return True
        return False

    def mint_open_version(self):
        my_version = OpenVersion()
        my_version.pdf_url = self.scraped_pdf_url
        my_version.metadata_url = self.scraped_open_metadata_url
        my_version.license = self.scraped_license
        my_version.doi = self.related_pub.doi
        my_version.source = self.open_version_source_string
        if self.is_open and not my_version.best_fulltext_url:
            my_version.metadata_url = self.url
        return my_version

    def scrape_for_fulltext_link(self):
        url = self.url
        is_journal = u"/doi/" in url or u"10." in url

        dont_scrape_list = [
                u"ncbi.nlm.nih.gov",
                u"elar.rsvpu.ru",  #these ones based on complaint in email
                u"elib.uraic.ru",
                u"elar.usfeu.ru",
                u"elar.urfu.ru",
                u"elar.uspu.ru"]

        if DEBUG_SCRAPING:
            print u"in scrape_for_fulltext_link, getting URL: {}".format(url)

        for url_fragment in dont_scrape_list:
            if url_fragment in url:
                print u"not scraping {} because is on our do not scrape list.".format(url)
                if "ncbi.nlm.nih.gov/pmc/articles/PMC" in url:
                    # pmc has fulltext
                    self.scraped_open_metadata_url = url
                    pmcid_matches = re.findall(".*(PMC\d+).*", url)
                    if pmcid_matches:
                        pmcid = pmcid_matches[0]
                        self.scraped_pdf_url = u"https://www.ncbi.nlm.nih.gov/pmc/articles/{}/pdf".format(pmcid)
                return

        try:
            with closing(http_get(url, stream=True, read_timeout=10, doi=self.doi)) as r:

                if is_response_too_large(r):
                    print "landing page is too large, skipping"
                    return

                # if our url redirects to a pdf, we're done.
                # = open repo http://hdl.handle.net/2060/20140010374
                if resp_is_pdf_from_header(r):

                    if DEBUG_SCRAPING:
                        print u"the head says this is a PDF. success! [{}]".format(url)
                    self.scraped_pdf_url = url
                    return

                else:
                    if DEBUG_SCRAPING:
                        print u"head says not a PDF for {}.  continuing more checks".format(url)

                # get the HTML tree
                page = r.content

                # set the license if we can find one
                scraped_license = find_normalized_license(page)
                if scraped_license:
                    self.scraped_license = scraped_license

                pdf_download_link = find_pdf_link(page, url)
                if pdf_download_link is not None:
                    if DEBUG_SCRAPING:
                        print u"found a PDF download link: {} {} [{}]".format(
                            pdf_download_link.href, pdf_download_link.anchor, url)

                    pdf_url = get_link_target(pdf_download_link, r.url)
                    if is_journal:
                        # if they are linking to a PDF, we need to follow the link to make sure it's legit
                        if DEBUG_SCRAPING:
                            print u"this is a journal. checking to see the PDF link actually gets a PDF [{}]".format(url)
                        if gets_a_pdf(pdf_download_link, r.url, self.doi):
                            self.scraped_pdf_url = pdf_url
                            self.scraped_open_metadata_url = url
                            return
                    else:
                        self.scraped_pdf_url = pdf_url
                        self.scraped_open_metadata_url = url
                        return

                # try this later because would rather get a pdfs
                # if they are linking to a .docx or similar, this is open.
                # this only works for repos... a ".doc" in a journal is not the article. example:
                # = closed journal http://doi.org/10.1007/s10822-012-9571-0
                if not is_journal:
                    doc_link = find_doc_download_link(page)
                    if doc_link is not None:
                        if DEBUG_SCRAPING:
                            print u"found a .doc download link {} [{}]".format(
                                get_link_target(doc_link, r.url), url)
                        self.scraped_open_metadata_url = url
                        return

        except requests.exceptions.ConnectionError:
            print u"ERROR: connection error on {} in scrape_for_fulltext_link, skipping.".format(url)
            return
        except requests.Timeout:
            print u"ERROR: timeout error on {} in scrape_for_fulltext_link, skipping.".format(url)
            return
        except requests.exceptions.InvalidSchema:
            print u"ERROR: InvalidSchema error on {} in scrape_for_fulltext_link, skipping.".format(url)
            return
        except requests.exceptions.RequestException as e:
            print u"ERROR: RequestException error on {} in scrape_for_fulltext_link, skipping.".format(url)
            return

        if DEBUG_SCRAPING:
            print u"found no PDF download link.  end of the line. [{}]".format(url)

        return self


    def __repr__(self):
        return u"<{} ({}) {}>".format(self.__class__.__name__, self.url, self.is_open)



class OpenPublisherWebpage(Webpage):
    open_version_source_string = u"publisher landing page"

    @property
    def is_open(self):
        return True


class PublisherWebpage(Webpage):
    open_version_source_string = u"publisher landing page"

    @property
    def is_open(self):
        if self.scraped_pdf_url or self.scraped_open_metadata_url:
            return True
        # just having the license isn't good enough
        return False


# abstract.  inherited from WebpageInOpenRepo and WebpageInUnknownRepo
class WebpageInRepo(Webpage):

    @property
    def open_version_source_string(self):
        if self.scraped_pdf_url or self.scraped_open_metadata_url:
            u"scraping of {}".format(self.base_open_version_source_string)
        return self.base_open_version_source_string


class WebpageInOpenRepo(WebpageInRepo):
    base_open_version_source_string = u"oa repository (via base-search.net oa url)"

    @property
    def is_open(self):
        return True


class WebpageInUnknownRepo(WebpageInRepo):
    base_open_version_source_string = u"oa repository (via base-search.net unknown-license url)"



def get_tree(page):
    page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
    try:
        tree = html.fromstring(page)
    except etree.XMLSyntaxError:
        print u"XMLSyntaxError in get_tree; not parsing."
        tree = None

    return tree




# = open journal http://www.emeraldinsight.com/doi/full/10.1108/00251740510597707
# = closed journal http://www.emeraldinsight.com/doi/abs/10.1108/14777261111143545


def gets_a_pdf(link, base_url, doi=None):

    if is_purchase_link(link):
        return False

    absolute_url = get_link_target(link, base_url)
    if DEBUG_SCRAPING:
        print u"checking to see if {} is a pdf".format(absolute_url)

    start = time()
    try:
        with closing(http_get(absolute_url, stream=True, read_timeout=10, doi=doi)) as r:
            if resp_is_pdf_from_header(r):
                if DEBUG_SCRAPING:
                    print u"http header says this is a PDF. took {}s {}".format(
                        elapsed(start), absolute_url)
                return True

            # everything below here needs to look at the content
            # so bail here if the page is too big
            if is_response_too_large(r):
                if DEBUG_SCRAPING:
                    print u"response is too big for more checks in gets_a_pdf"
                return False

            # some publishers send a pdf back wrapped in an HTML page using frames.
            # this is where we detect that, using each publisher's idiosyncratic templates.
            # we only check based on a whitelist of publishers, because downloading this whole
            # page (r.content) is expensive to do for everyone.
            if 'onlinelibrary.wiley.com' in absolute_url:
                # = closed journal http://doi.org/10.1111/ele.12585
                # = open journal http://doi.org/10.1111/ele.12587 cc-by
                if '<iframe' in r.content:
                    if DEBUG_SCRAPING:
                        print u"this is a Wiley 'enhanced PDF' page. took {}s [{}]".format(
                            elapsed(start), absolute_url)
                    return True

            elif 'ieeexplore' in absolute_url:
                # (this is a good example of one dissem.in misses)
                # = open journal http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6740844
                # = closed journal http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6045214
                if '<frame' in r.content:
                    if DEBUG_SCRAPING:
                        print u"this is a IEEE 'enhanced PDF' page. took {}s [{}]".format(
                                    elapsed(start), absolute_url)
                    return True

            elif 'sciencedirect' in absolute_url:
                if u"does not support the use of the crawler software" in r.content:
                    return True


        if DEBUG_SCRAPING:
            print u"we've decided this ain't a PDF. took {}s [{}]".format(
                elapsed(start), absolute_url)
        return False
    except requests.exceptions.ConnectionError:
        print u"ERROR: connection error in gets_a_pdf, skipping."
        return False
    except requests.Timeout:
        print u"ERROR: timeout error in gets_a_pdf, skipping."
        return False
    except requests.exceptions.InvalidSchema:
        print u"ERROR: InvalidSchema error in gets_a_pdf, skipping."
        return False
    except requests.exceptions.RequestException:
        print u"ERROR: RequestException error in gets_a_pdf, skipping."
        return False



def find_doc_download_link(page):
    tree = get_tree(page)
    for link in get_useful_links(tree):
        # there are some links that are FOR SURE not the download for this article
        if has_bad_href_word(link.href):
            continue

        if has_bad_anchor_word(link.anchor):
            continue

        # = open repo https://lirias.kuleuven.be/handle/123456789/372010
        if ".doc" in link.href or ".doc" in link.anchor:
            return link

    return None


# it matters this is just using the header, because we call it even if the content
# is too large.  if we start looking in content, need to break the pieces apart.
def resp_is_pdf_from_header(resp):
    looks_good = False

    for k, v in resp.headers.iteritems():
        if v:
            key = k.lower()
            val = v.lower()

            if key == "content-type" and "application/pdf" in val:
                looks_good = True

            if key =='content-disposition' and "pdf" in val:
                looks_good = True

    return looks_good


class DuckLink(object):
    def __init__(self, href, anchor):
        self.href = href
        self.anchor = anchor


def get_useful_links(tree):
    ret = []
    if tree is None:
        return ret

    # remove related content sections
    # gets rid of these bad links: http://www.tandfonline.com/doi/abs/10.4161/auto.19496
    for related_content in tree.xpath("//div[@class=\'relatedItem\']"):
        # tree.getparent().remove(related_content)
        related_content.clear()

    # now get the links
    links = tree.xpath("//a")

    for link in links:
        link_text = link.text_content().strip().lower()
        if link_text:
            link.anchor = link_text
            if "href" in link.attrib:
                link.href = link.attrib["href"]

        else:
            # also a useful link if it has a solo image in it, and that image includes "pdf" in its filename
            link_content_elements = [l for l in link]
            if len(link_content_elements)==1:
                link_insides = link_content_elements[0]
                if link_insides.tag=="img":
                    if "src" in link_insides.attrib and "pdf" in link_insides.attrib["src"]:
                        link.anchor = u"image: {}".format(link_insides.attrib["src"])
                        if "href" in link.attrib:
                            link.href = link.attrib["href"]

        if hasattr(link, "anchor") and hasattr(link, "href"):
            ret.append(link)

    return ret


def is_purchase_link(link):
    # = closed journal http://www.sciencedirect.com/science/article/pii/S0147651300920050
    if "purchase" in link.anchor:
        print u"found a purchase link!", link.anchor, link.href
        return True

    return False

def has_bad_href_word(href):
    href_blacklist = [
        # = closed 10.1021/acs.jafc.6b02480
        # editorial and advisory board
        "/eab/",

        # = closed 10.1021/acs.jafc.6b02480
        "/suppl_file/",

        # https://lirias.kuleuven.be/handle/123456789/372010
        "supplementary+file",

        # http://www.jstor.org/action/showSubscriptions
        "showsubscriptions",

        # 10.7763/ijiet.2014.v4.396
        "/faq",

        # 10.1515/fabl.1988.29.1.21
        "{{",

        # 10.2174/1389450116666150126111055
        "cdt-flyer",

        # 10.1111/fpa.12048
        "figures",

        # prescribing information, see http://www.nejm.org/doi/ref/10.1056/NEJMoa1509388#t=references
        "janssenmd.com",

        # prescribing information, see http://www.nejm.org/doi/ref/10.1056/NEJMoa1509388#t=references
        "community-register",

        # prescribing information, see http://www.nejm.org/doi/ref/10.1056/NEJMoa1509388#t=references
        "quickreference",

        # 10.4158/ep.14.4.458
        "libraryrequestform",

        # http://www.nature.com/nutd/journal/v6/n7/full/nutd201620a.html
        "iporeport",

        #https://ora.ox.ac.uk/objects/uuid:06829078-f55c-4b8e-8a34-f60489041e2a
        "no_local_copy"
    ]
    for bad_word in href_blacklist:
        if bad_word in href.lower():
            return True
    return False


def has_bad_anchor_word(anchor_text):
    anchor_blacklist = [
        # = closed repo https://works.bepress.com/ethan_white/27/
        "user",
        "guide",

        # = closed 10.1038/ncb3399
        "checklist",

        # https://hal.archives-ouvertes.fr/hal-00085700
        "metadata from the pdf file",
        u"récupérer les métadonnées à partir d'un fichier pdf",

        # = closed http://europepmc.org/abstract/med/18998885
        "bulk downloads",

        # = closed 10.1021/acs.jafc.6b02480
        "masthead",

        # closed http://eprints.soton.ac.uk/342694/
        "download statistics",

        # no examples for these yet
        "supplement",
        "figure",
        "faq"
    ]
    for bad_word in anchor_blacklist:
        if bad_word in anchor_text.lower():
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

        # there are some links that are SURELY NOT the pdf for this article
        if has_bad_href_word(link.href):
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

