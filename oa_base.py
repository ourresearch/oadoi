#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import datetime
import sys
import requests
import random
from time import time
from Levenshtein import ratio
from collections import defaultdict
from HTMLParser import HTMLParser
from sqlalchemy import sql
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.attributes import flag_modified
import shortuuid

from app import db
from app import logger
from webpage import WebpageInOpenRepo
from webpage import WebpageInUnknownRepo
from webpage import WebpageInClosedRepo
from oa_local import find_normalized_license
from oa_pdf import convert_pdf_to_txt
from util import elapsed
from util import normalize
from util import remove_punctuation


DEBUG_BASE = True


class BaseResponseAddin():
    @property
    def doc(self):
        if not self.body:
            return
        return self.body.get("_source", None)

    @property
    def is_base1(self):
        return self.doc["oa"] == 1

    @property
    def is_base2(self):
        return self.doc["oa"] == 1

    def get_webpages_for_fulltext_urls(self):
        response = []

        license = find_normalized_license(self.fulltext_license)

        if self.fulltext_urls:
            for scrape_results in self.fulltext_urls:
                if self.is_base1:
                    my_webpage = WebpageInOpenRepo(url=scrape_results.get("pdf_landing_page", None))
                else:
                    my_webpage = WebpageInUnknownRepo(url=scrape_results.get("pdf_landing_page", None))
                my_webpage.scraped_pdf_url = scrape_results.get("free_pdf_url", None)
                my_webpage.scraped_open_metadata_url = scrape_results.get("pdf_landing_page", None)
                my_webpage.scraped_license = license
                my_webpage.base_doc = self.doc
                response.append(my_webpage)

        # eventually these will have fulltext_url_dicts populated as well
        else:
            for url in get_urls_from_base_doc(self.doc):
                if self.id.startswith("ftarxiv") or self.id.startswith("ftpubmed") or self.id.startswith("ftciteseer"):
                    my_webpage = WebpageInOpenRepo(url=url)
                    my_webpage.scraped_open_metadata_url = url

                    # this will get handled when the oa1 urls get added
                    pmcid_matches = re.findall(".*(PMC\d+).*", url)
                    if pmcid_matches:
                        pmcid = pmcid_matches[0]
                        my_webpage.scraped_pdf_url = u"https://www.ncbi.nlm.nih.gov/pmc/articles/{}/pdf".format(pmcid)
                else:
                    my_webpage = WebpageInClosedRepo(url=url)

                my_webpage.scraped_license = license
                my_webpage.base_doc = self.doc
                response.append(my_webpage)

        return response



    def get_base_matches(self, my_pub, match_type, do_scrape=True):
        base_matches = []

        try:
            for my_webpage in self.get_webpages_for_fulltext_urls():
                my_base_match = BaseMatch()
                my_base_match.scrape_updated = datetime.datetime.utcnow().isoformat()
                my_base_match.doi = my_pub.doi
                my_base_match.url = my_webpage.url
                my_base_match.base_id = self.id

                if my_webpage.is_open:
                    my_base_match.scrape_evidence = my_webpage.open_version_source_string
                    my_base_match.scrape_pdf_url = my_webpage.scraped_pdf_url
                    my_base_match.scrape_metadata_url = my_webpage.scraped_open_metadata_url
                    my_base_match.scrape_license = my_webpage.scraped_license
                    if do_scrape:
                        my_base_match.scrape_version = my_base_match.find_version()

                base_matches.append(my_base_match)

        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            logger.info(u'decoding JSON has failed base response')
            pass

        return base_matches


class BaseTitleView(db.Model, BaseResponseAddin):
    id = db.Column(db.Text, db.ForeignKey('base.id'), primary_key=True)
    collection = db.Column(db.Text)
    doi = db.Column(db.Text)
    title = db.Column(db.Text)
    normalized_title = db.Column(db.Text, db.ForeignKey('crossref_title_view.normalized_title'))
    body = db.Column(JSONB)
    fulltext_updated = db.Column(db.DateTime)
    fulltext_urls = db.Column(JSONB)
    fulltext_license = db.Column(db.Text)


class BaseMatch(db.Model):
    id = db.Column(db.Text, primary_key=True)
    base_id = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'))
    url = db.Column(db.Text)

    scrape_updated = db.Column(db.DateTime)
    scrape_evidence = db.Column(db.Text)
    scrape_pdf_url = db.Column(db.Text)
    scrape_metadata_url = db.Column(db.Text)
    scrape_version = db.Column(db.Text)
    scrape_license = db.Column(db.Text)

    error = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.error = ""

    @property
    def is_open(self):
        return (self.scrape_evidence and self.scrape_evidence != "closed")

    def find_version(self):
        if not self.scrape_pdf_url:
            return None

        try:
            text = convert_pdf_to_txt(self.scrape_pdf_url)
            # logger.info(text)
            if text:
                patterns = [
                    re.compile(ur"©.?\d{4}", re.UNICODE),
                    re.compile(ur"copyright \d{4}", re.IGNORECASE),
                    re.compile(ur"all rights reserved", re.IGNORECASE),
                    re.compile(ur"This article is distributed under the terms of the Creative Commons", re.IGNORECASE),
                    re.compile(ur"this is an open access article", re.IGNORECASE)
                    ]
                for pattern in patterns:
                    matches = pattern.findall(text)
                    if matches:
                        return "publishedVersion"
        except Exception as e:
            self.error += u"Exception doing convert_pdf_to_txt on {}! investigate! {}".format(self.scrape_pdf_url, unicode(e.message).encode("utf-8"))
            logger.info(self.error)

        return None


class Base(db.Model, BaseResponseAddin):
    id = db.Column(db.Text, primary_key=True)
    collection = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'))
    body = db.Column(JSONB)
    fulltext_updated = db.Column(db.DateTime)
    fulltext_urls = db.Column(JSONB)
    fulltext_license = db.Column(db.Text)

    def set_doc(self, doc):
        if not self.body:
            self.body = {}
        self.body["_source"] = doc

    def update_doc(self):
        self.set_fulltext_urls()
        action_record = self.make_action_record()
        self.doc = action_record["doc"]


    def scrape_for_fulltext(self):
        self.set_webpages()
        response_webpages = []

        found_open_fulltext = False
        for my_webpage in self.webpages:
            if not found_open_fulltext:
                my_webpage.scrape_for_fulltext_link()
                if my_webpage.has_fulltext_url:
                    logger.info(u"** found an open copy! {}".format(my_webpage.fulltext_url))
                    found_open_fulltext = True
                    response_webpages.append(my_webpage)

        self.open_webpages = response_webpages
        sys.exc_clear()  # someone on the internet said this would fix All The Memory Problems. has to be in the thread.
        return self

    def set_webpages(self):
        self.open_webpages = []
        self.webpages = []
        for my_webpage in self.get_webpages_for_fulltext_urls():
            self.webpages.append(my_webpage)


    def set_fulltext_urls(self):

        self.fulltext_urls = []
        self.fulltext_license = None

        # first set license if there is one originally.  overwrite it later if scraped a better one.
        if "license" in self.doc and self.doc["license"]:
            self.fulltext_license = find_normalized_license(self.doc["license"])

        for my_webpage in self.open_webpages:
            if my_webpage.has_fulltext_url:
                response = {}
                # logger.info(u"setting self.fulltext_urls")
                self.fulltext_urls += [{"free_pdf_url": my_webpage.scraped_pdf_url, "pdf_landing_page": my_webpage.url}]
                if not self.fulltext_license or self.fulltext_license == "unknown":
                    self.fulltext_license = my_webpage.scraped_license
            else:
                logger.info(u"{} has no fulltext url alas".format(my_webpage))

        if self.fulltext_license == "unknown":
            self.fulltext_license = None

        # logger.info(u"set self.fulltext_urls to {}".format(self.fulltext_urls))


    def make_action_record(self):
        update_fields = {
            "random": random.random(),
            "fulltext_updated": self.fulltext_updated,
            "fulltext_url_dicts": self.fulltext_url_dicts,
            "fulltext_license": self.fulltext_license,
        }

        self.doc.update(update_fields)
        action = {"doc": self.doc}
        action["_id"] = self.doc["id"]
        return action



    def reset(self):
        self.collection = self.id.split(":")[0]
        self.fulltext_updated = datetime.datetime.utcnow().isoformat()
        self.fulltext_url_dicts = []
        self.fulltext_license = None
        self.set_webpages()


    def find_fulltext(self):
        scrape_start = time()
        self.reset()
        # mark the body as dirty, otherwise sqlalchemy doesn't know, doesn't save it
        flag_modified(self, "body")
        self.scrape_for_fulltext()
        self.set_fulltext_urls()
        action_record = self.make_action_record()
        self.body = {"_id": self.id, "_source": action_record["doc"]}
        logger.info(u"find_fulltext took {} seconds".format(elapsed(scrape_start, 2)))



    def __repr__(self):
        return u"<Base ({})>".format(self.id)



def get_urls_from_base_doc(doc):
    if not doc:
        logger.info(u"no doc in get_urls_from_base_doc, so returning.")
        return []

    response = []

    # highwire says articles are OA but they aren't.
    # example: https://www.base-search.net/Search/Results?lookfor=Democracy%2C+Elections+and+the+End+of+History&type=tit&oaboost=1&ling=1&name=&thes=&refid=dcresen&newsearch=1
    untrustworthy_base_collections = ["fthighwire"]
    for base_collection in untrustworthy_base_collections:
        if doc["id"].startswith(base_collection):
            # logger.info(u"not using the base response from {} because in untrustworthy_base_collections".format(base_collection))
            return response

    if "urls" in doc:
        # pmc can only add pmc urls.  otherwise has junk about dois that aren't actually open.
        if "sources" in doc and doc["sources"] and u"PubMed Central (PMC)" in doc["sources"]:
            for url in doc["urls"]:
                if "/pmc/" in url and url != "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
                    response += [url]
        else:
            response += doc["urls"]

    # oxford IR doesn't return URLS, instead it returns IDs from which we can build URLs
    # example: https://www.base-search.net/Record/5c1cf4038958134de9700b6144ae6ff9e78df91d3f8bbf7902cb3066512f6443/
    if "sources" in doc and doc["sources"] and "Oxford University Research Archive (ORA)" in doc["sources"]:
        if "relations" in doc and doc["relations"]:
            for relation in doc["relations"]:
                if relation.startswith("uuid"):
                    response += [u"https://ora.ox.ac.uk/objects/{}".format(relation)]

    # filter out some urls that BASE data says are open but are actually closed
    blacklist_url_snippets = [
        # these are base1s but are actually closed.  examples:  https://www.base-search.net/Search/Results?lookfor=+http%3A%2F%2Fdx.doi.org%2F10.1093%2Fanalys&type=all&oaboost=1&ling=1&name=&thes=&refid=dcresen&newsearch=1
        u"/10.1093/analys/",
        u"academic.oup.com/analysis",
        u"analysis.oxfordjournals.org/",
        u"ncbi.nlm.nih.gov/pubmed/",
        u"gateway.webofknowledge.com/"
    ]
    for url_snippet in blacklist_url_snippets:
        response = [url for url in response if url_snippet not in url]


    # filter out all the urls that go straight to publisher pages from base response
    # filter out doi urls unless they are the only url
    if len(response) > 1:
        response = [url for url in response if u"doi.org/" not in url]



    # and then html unescape them, because some are html escaped
    h = HTMLParser()
    response = [h.unescape(url) for url in response]

    return response


def normalize_title_for_querying(title):
    if not title:
        return ""
    title_to_query = ""
    title = title.lower()
    # can't just replace all punctuation because ' replaced with ? gets no hits
    title = title.replace('"', "?")
    title = title.replace('#', "?")
    title = title.replace('=', "?")
    title = title.replace('&', "?")
    title = title.replace('%', "?")
    title = title.replace('/', "?")
    title = title.replace('!', "?")
    # title = title.replace('-', "*")

    # only bother looking up titles that are at least 3 words long
    title_words = title.split()
    if len(title_words) >= 2:
        # only look up the first 12 words
        title_to_query = u" ".join(title_words[0:12])

    return title_to_query


def title_good_for_querying(title):
    if title and len(title) >= 15:
        return True
    return False



def title_is_too_common(normalized_title):
    # these common titles were determined using this SQL,
    # which lists the titles of BASE hits that matched titles of more than 2 articles in a sample of 100k articles.
    # ugly sql, i know.  but better to include here as a comment than not, right?
    #     select norm_title, count(*) as c from (
    #     select id, response_jsonb->>'free_fulltext_url' as url, api->'_source'->>'title' as title, normalize_title_v2(api->'_source'->>'title') as norm_title
    #     from crossref where response_jsonb->>'free_fulltext_url' in
    #     ( select url from (
    #     select response_jsonb->>'free_fulltext_url' as url, count(*) as c
    #     from crossref
    #     where crossref.response_jsonb->>'free_fulltext_url' is not null
    #     and id in (select id from dois_random_articles_1mil_do_hybrid_100k limit 100000)
    #     group by url
    #     order by c desc) s where c > 1 ) limit 1000 ) ss group by norm_title order by c desc
    # and then have added more to it

    common_title_string = """
    informationreaders
    editorialboardpublicationinformation
    insidefrontcovereditorialboard
    graphicalcontentslist
    instructionsauthors
    reviewsandnoticesbooks
    editorialboardaimsandscope
    contributorsthisissue
    parliamentaryintelligence
    editorialadvisoryboard
    informationauthors
    instructionscontributors
    royalsocietymedicine
    guesteditorsintroduction
    cumulativesubjectindexvolumes
    acknowledgementreviewers
    medicalsocietylondon
    ouvragesrecuslaredaction
    royalmedicalandchirurgicalsociety
    moderntechniquetreatment
    reviewcurrentliterature
    answerscmeexamination
    publishersannouncement
    cumulativeauthorindex
    abstractsfromcurrentliterature
    booksreceivedreview
    royalacademymedicineireland
    editorialsoftwaresurveysection
    cumulativesubjectindex
    acknowledgementreferees
    specialcorrespondence
    atmosphericelectricity
    classifiedadvertising
    softwaresurveysection
    abstractscurrentliterature
    britishmedicaljournal
    veranstaltungskalender
    internationalconference
    """

    for common_title in common_title_string.split("\n"):
        if normalized_title==common_title.strip():
            return True
    return False





def refresh_base_matches(my_pub, do_scrape=True):
    my_pub.base_matches = []

    start_time = time()

    if not my_pub:
        return

    for base_obj in my_pub.base_doi_links:
        if do_scrape:
            base_obj.find_fulltext()
        doc = base_obj.body["_source"]
        match_type = "doi"
        my_pub.base_matches += base_obj.get_base_matches(my_pub, match_type, do_scrape=do_scrape)

    if not my_pub.normalized_title:
        # logger.info(u"title '{}' is too short to match BASE by title".format(my_pub.best_title))
        return
    if title_is_too_common(my_pub.normalized_title):
        # logger.info(u"title '{}' is too common to match BASE by title".format(my_pub.best_title))
        return

    if my_pub.normalized_titles:
        crossref_title_hit = my_pub.normalized_titles[0]
        for base_title_obj in crossref_title_hit.matching_base_title_views:
            if do_scrape:
                base_obj = db.session.query(Base).get(base_title_obj.id)
                base_obj.find_fulltext()
                base_title_obj = base_obj
            match_type = None
            doc = base_title_obj.body["_source"]
            if my_pub.first_author_lastname or my_pub.last_author_lastname:
                if doc.get("authors", None):
                    try:
                        base_doc_author_string = u", ".join(doc["authors"])
                        if my_pub.first_author_lastname and normalize(my_pub.first_author_lastname) in normalize(base_doc_author_string):
                            match_type = "title and first author"
                        elif my_pub.last_author_lastname and normalize(my_pub.last_author_lastname) in normalize(base_doc_author_string):
                            match_type = "title and last author"
                        else:
                            if DEBUG_BASE:
                                logger.info(u"author check fails, so skipping this record. Looked for {} and {} in {}".format(
                                    my_pub.first_author_lastname, my_pub.last_author_lastname, base_doc_author_string))
                                logger.info(my_pub.authors)
                            continue
                    except TypeError:
                        pass # couldn't make author string
            if not match_type:
                match_type = "title"
            my_pub.base_matches += base_title_obj.get_base_matches(my_pub, match_type, do_scrape=do_scrape)

    # print "my_pub.base_matches", my_pub.base_matches
    # import pdb; pdb.set_trace()

    # logger.info(u"finished base step of set_fulltext_urls with in {}s".format(
    #     elapsed(start_time, 2)))

    return my_pub.base_matches




# titles_string = remove_punctuation("Authors from the periphery countries choose open access more often (preprint)")
# url_template = u"https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi?func=PerformSearch&query=dctitle:({titles_string})&format=json"
# url = url_template.format(titles_string=titles_string)
# logger.info(u"calling base with {}".format(url))
#
# proxy_url = os.getenv("STATIC_IP_PROXY")
# proxies = {"https": proxy_url}
# r = requests.get(url, proxies=proxies, timeout=6)
# r.json()
# id_string = "{}{}".format(dccollection, dcdoi)

