#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import os
import requests
from requests.auth import HTTPProxyAuth
import re
from time import time
from lxml import html
from lxml import etree
from contextlib import closing

from oa_local import find_normalized_license
from open_location import OpenLocation
from http_cache import http_get
from util import is_doi_url
from util import elapsed
from util import get_tree
from util import get_link_target
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
        self.match_type = None
        self.base_id = None
        self.base_doc = None
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
    def publisher(self):
        if self.related_pub:
            return self.related_pub.publisher
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

    def mint_open_location(self):
        my_location = OpenLocation()
        my_location.pdf_url = self.scraped_pdf_url
        my_location.metadata_url = self.scraped_open_metadata_url
        my_location.license = self.scraped_license
        my_location.doi = self.related_pub.doi
        my_location.evidence = self.open_version_source_string
        my_location.match_type = self.match_type
        my_location.base_id = self.base_id
        my_location.base_doc = self.base_doc
        if self.is_open and not my_location.best_fulltext_url:
            my_location.metadata_url = self.url
        return my_location

    def scrape_for_fulltext_link(self):
        url = self.url
        check_if_links_accessible = True

        dont_scrape_list = [
                u"ncbi.nlm.nih.gov",
                u"pubmed",
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
            with closing(http_get(url, stream=True, read_timeout=10, related_pub=self.related_pub)) as r:

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

                    pdf_url = get_link_target(pdf_download_link.href, r.url)
                    if check_if_links_accessible:
                        # if they are linking to a PDF, we need to follow the link to make sure it's legit
                        if DEBUG_SCRAPING:
                            print u"checking to see the PDF link actually gets a PDF [{}]".format(url)
                        if gets_a_pdf(pdf_download_link, r.url, self.related_pub):
                            self.scraped_pdf_url = pdf_url
                            self.scraped_open_metadata_url = url
                            return
                    else:
                        self.scraped_pdf_url = pdf_url
                        self.scraped_open_metadata_url = url
                        return

                # try this later because would rather get a pdfs
                # if they are linking to a .docx or similar, this is open.
                doc_link = find_doc_download_link(page)
                if doc_link is not None:
                    if DEBUG_SCRAPING:
                        print u"found a .doc download link {} [{}]".format(
                            get_link_target(doc_link.href, r.url), url)
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

    def scrape_for_fulltext_link(self):
        url = self.url

        if DEBUG_SCRAPING:
            print u"checking to see if {} says it is open".format(url)

        start = time()
        try:
            with closing(http_get(url, stream=True, read_timeout=30, related_pub=self.related_pub, use_proxy=True)) as r:
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

                page = r.content

                pdf_download_link = find_pdf_link(page, self.url)
                if pdf_download_link is not None:
                    pdf_url = get_link_target(pdf_download_link.href, r.url)
                    if gets_a_pdf(pdf_download_link, r.url, self.related_pub, use_proxy=True):
                        self.scraped_pdf_url = pdf_url
                        self.scraped_open_metadata_url = self.url
                        self.open_version_source_string = "hybrid (via free pdf)"

                license_patterns = [u"(creativecommons.org\/licenses\/[a-z\-]+)",
                            u"distributed under the terms (.*) which permits",
                            u"This is an open access article under the terms (.*) which permits",
                            u"This is an open access article published under (.*) which permits",
                            u'<div class="openAccess-articleHeaderContainer(.*?)</div>'
                            ]
                for pattern in license_patterns:
                    matches = re.findall(pattern, page, re.IGNORECASE)
                    if matches:
                        self.scraped_license = find_normalized_license(matches[0])
                        self.scraped_open_metadata_url = self.url
                        self.open_version_source_string = "hybrid (via page says license)"

                says_open_access_patterns = [("Informa UK Limited", u"/accessOA.png"),
                            ("Oxford University Press (OUP)", u"<i class='icon-availability_open'"),
                            ("Institute of Electrical & Electronics Engineers (IEEE)", u'"isOpenAccess":true'),
                            ("Informa UK Limited", u"/accessOA.png"),
                            ("Royal Society of Chemistry (RSC)", u"/open_access_blue.png"),
                            ("Cambridge University Press (CUP)", u'<span class="icon access open-access cursorDefault">')
                            ]
                for (publisher, pattern) in says_open_access_patterns:
                    matches = re.findall(pattern, page, re.IGNORECASE)
                    if self.publisher == publisher and matches:
                        self.scraped_license = None  # could get it by following url but out of scope for now
                        self.scraped_open_metadata_url = self.url
                        self.open_version_source_string = "hybrid (via page says Open Access)"

            if self.is_open:
                if DEBUG_SCRAPING:
                    print u"we've decided this is open! took {} seconds [{}]".format(
                        elapsed(start), url)
                return True
            else:
                if DEBUG_SCRAPING:
                    print u"we've decided this doesn't say open. took {} seconds [{}]".format(
                        elapsed(start), url)
                return False
        except requests.exceptions.ConnectionError:
            print u"ERROR: connection error in says_open on {}, skipping.".format(url)
            return False
        except requests.Timeout:
            print u"ERROR: timeout error in says_open on {}, skipping.".format(url)
            return False
        except requests.exceptions.InvalidSchema:
            print u"ERROR: InvalidSchema error in says_open on {}, skipping.".format(url)
            return False
        except requests.exceptions.RequestException:
            print u"ERROR: RequestException error in says_open on {}, skipping.".format(url)
            return False

    @property
    def is_open(self):
        if self.scraped_pdf_url or self.scraped_open_metadata_url:
            return True
        # just having the license isn't good enough
        return False


# abstract.  inherited from WebpageInOpenRepo and WebpageInUnknownRepo
class WebpageInRepo(Webpage):
    @property
    def base_open_version_source_string(self):
        if self.match_type:
            return u"oa repository (via BASE {} match)".format(self.match_type)
        return u"oa repository (via BASE)"

    @property
    def open_version_source_string(self):
        return self.base_open_version_source_string


class WebpageInClosedRepo(WebpageInRepo):
    @property
    def is_open(self):
        return False


class WebpageInOpenRepo(WebpageInRepo):
    @property
    def is_open(self):
        return True


class WebpageInUnknownRepo(WebpageInRepo):
    pass





def gets_a_pdf(link, base_url, related_pub=None, use_proxy=False):

    if is_purchase_link(link):
        return False

    absolute_url = get_link_target(link.href, base_url)
    if DEBUG_SCRAPING:
        print u"checking to see if {} is a pdf".format(absolute_url)

    start = time()
    try:
        with closing(http_get(absolute_url, stream=True, read_timeout=10, related_pub=related_pub, use_proxy=use_proxy)) as r:
            if resp_is_pdf_from_header(r):
                if DEBUG_SCRAPING:
                    print u"http header says this is a PDF. took {} seconds {}".format(
                        elapsed(start), absolute_url)
                return True

            # everything below here needs to look at the content
            # so bail here if the page is too big
            if is_response_too_large(r):
                if DEBUG_SCRAPING:
                    print u"response is too big for more checks in gets_a_pdf"
                return False

            if related_pub:
                says_free_patterns = [("Wiley-Blackwell", u'<span class="freeAccess" title="You have free access to this content">'),
                            ]
                for (publisher, pattern) in says_free_patterns:
                    matches = re.findall(pattern, r.content, re.IGNORECASE)
                    if related_pub.publisher == publisher and matches:
                        return True

        if DEBUG_SCRAPING:
            print u"we've decided this ain't a PDF. took {} seconds [{}]".format(
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

    # references and related content sections
    bad_section_finders = [
        "//div[@class=\'relatedItem\']",  #http://www.tandfonline.com/doi/abs/10.4161/auto.19496
        "//div[@class=\'citedBySection\']"  #10.3171/jns.1966.25.4.0458
    ]
    for section_finder in bad_section_finders:
        for bad_section in tree.xpath(section_finder):
            bad_section.clear()

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

        # https://www.crossref.org/iPage?doi=10.3138%2Fecf.22.1.1
        "price-lists",

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

        # wrong link
        "abstracts",

        # https://hal.archives-ouvertes.fr/hal-00085700
        "metadata from the pdf file",
        u"récupérer les métadonnées à partir d'un fichier pdf",

        # = closed http://europepmc.org/abstract/med/18998885
        "bulk downloads",

        # http://www.utpjournals.press/doi/pdf/10.3138/utq.35.1.47
        "license agreement",

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

    if DEBUG_SCRAPING:
        print u"in find_pdf_link with {}".format(url)

    tree = get_tree(page)
    if tree is None:
        return None

    # before looking in links, look in meta for the pdf link
    # = open journal http://onlinelibrary.wiley.com/doi/10.1111/j.1461-0248.2011.01645.x/abstract
    # = open journal http://doi.org/10.1002/meet.2011.14504801327
    # = open repo http://hdl.handle.net/10088/17542
    # = open http://handle.unsw.edu.au/1959.4/unsworks_38708 cc-by

    # print page

    if "citation_pdf_url" in page:
        if DEBUG_SCRAPING:
            print u"found citation_pdf_url in page"
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




