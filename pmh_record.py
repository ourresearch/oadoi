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
import shortuuid

from app import db
from app import logger
from page import Page
from webpage import WebpageInBaseRepo
from webpage import WebpageInPmhRepo
from oa_local import find_normalized_license
from oa_pdf import convert_pdf_to_txt
from util import elapsed
from util import normalize
from util import remove_punctuation


DEBUG_BASE = False

class PmhRecord(db.Model):
    id = db.Column(db.Text, primary_key=True)
    source = db.Column(db.Text)
    doi = db.Column(db.Text)
    record_timestamp = db.Column(db.DateTime)
    api_raw = db.Column(JSONB)
    title = db.Column(db.Text)
    license = db.Column(db.Text)
    oa = db.Column(db.Text)
    urls = db.Column(JSONB)
    authors = db.Column(JSONB)
    relations = db.Column(JSONB)
    sources = db.Column(JSONB)
    updated = db.Column(db.DateTime)
    started = db.Column(db.DateTime)
    finished = db.Column(db.DateTime)
    rand = db.Column(db.Numeric)

    # pages = db.relationship(
    #     'Page',
    #     lazy='subquery',
    #     cascade="all, delete-orphan",
    #     # no backref.  we don't want page to link to this
    #     foreign_keys="Page.id"
    # )

    def __init__(self, **kwargs):
        self.updated = datetime.datetime.utcnow().isoformat()
        super(self.__class__, self).__init__(**kwargs)


    def get_good_urls(self):
        valid_urls = []

        # pmc can only add pmc urls.  otherwise has junk about dois that aren't actually open.
        if self.urls:
            if "oai:pubmedcentral.nih.gov" in self.id:
                for url in self.urls:
                    if "/pmc/" in url and url != "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
                        pmcid_matches = re.findall(".*(PMC\d+).*", url)
                        if pmcid_matches:
                            pmcid = pmcid_matches[0]
                            url = u"https://www.ncbi.nlm.nih.gov/pmc/articles/{}".format(pmcid)
                            valid_urls.append(url)
            else:
                valid_urls += [url for url in self.urls if url and url.startswith(u"http")]

        # filter out doi urls unless they are the only url
        # might be a figshare url etc, but otherwise is usually to a publisher page which
        # may or may not be open, and we are handling through hybrid path
        if len(valid_urls) > 1:
            valid_urls = [url for url in valid_urls if u"doi.org/" not in url]

        # filter out some urls that we know are closed
        blacklist_url_snippets = [
            u"/10.1093/analys/",
            u"academic.oup.com/analysis",
            u"analysis.oxfordjournals.org/",
            u"ncbi.nlm.nih.gov/pubmed/",
            u"gateway.webofknowledge.com/"
        ]
        for url_snippet in blacklist_url_snippets:
            valid_urls = [url for url in valid_urls if url_snippet not in url]


        # oxford IR doesn't return URLS, instead it returns IDs from which we can build URLs
        # example: https://www.base-search.net/Record/5c1cf4038958134de9700b6144ae6ff9e78df91d3f8bbf7902cb3066512f6443/
        if self.sources and "Oxford University Research Archive (ORA)" in self.sources:
            if self.relation:
                for relation in self.relation:
                    if relation.startswith("uuid"):
                        valid_urls += [u"https://ora.ox.ac.uk/objects/{}".format(relation)]

        # and then html unescape them, because some are html escaped
        h = HTMLParser()
        valid_urls = [h.unescape(url) for url in valid_urls]

        return valid_urls



    def make_pages(self):
        print "in make_pages"
        self.pages = []

        for url in self.get_good_urls():
            my_page = Page()
            my_page.id = self.id
            my_page.url = url
            my_page.doi = self.doi
            my_page.title = self.title
            # my_page.authors = self.authors
            print u"my_page", my_page
            self.pages.append(my_page)

        print "done make_pages"
        return self.pages


    def __repr__(self):
        return u"<PmhRecord ({}) doi:{} '{}'>".format(self.id, self.doi, self.title)


# legacy, just used for matching
class BaseMatch(db.Model):
    id = db.Column(db.Text, primary_key=True)
    base_id = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey('pub.id'))
    url = db.Column(db.Text)
    scrape_updated = db.Column(db.DateTime)
    scrape_evidence = db.Column(db.Text)
    scrape_pdf_url = db.Column(db.Text)
    scrape_metadata_url = db.Column(db.Text)
    scrape_version = db.Column(db.Text)
    scrape_license = db.Column(db.Text)
    updated = db.Column(db.DateTime)

    @property
    def is_open(self):
        return self.scrape_metadata_url or self.scrape_pdf_url





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
    informationcontributors
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





def refresh_green_locations(my_pub, do_scrape=True):
    green_locations = []

    start_time = time()

    if not my_pub:
        return

    for pmh_record_obj in my_pub.pmh_record_doi_links:
        match_type = "doi"
        green_locations += pmh_record_obj.make_pages()

    if not my_pub.normalized_title:
        # logger.info(u"title '{}' is too short to match BASE by title".format(my_pub.best_title))
        return

    if title_is_too_common(my_pub.normalized_title):
        # logger.info(u"title '{}' is too common to match BASE by title".format(my_pub.best_title))
        return

    if my_pub.normalized_titles:
        crossref_title_hit = my_pub.normalized_titles[0]
        for pmh_record_title_obj in crossref_title_hit.matching_pmh_record_title_views:
            match_type = None
            if my_pub.first_author_lastname or my_pub.last_author_lastname:
                pmh_record_authors = pmh_record_title_obj.authors
                if pmh_record_authors:
                    try:
                        base_doc_author_string = u", ".join(pmh_record_authors)
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
            green_locations += pmh_record_title_obj.make_pages()

    green_locations_dict = {}
    for loc in green_locations:
        # do it this way so dois get precedence because they happened first
        if not loc.id+loc.url in green_locations_dict:
            green_locations_dict[loc.id+loc.url] = loc

    my_pub.green_location_matches = green_locations_dict.values()
    if do_scrape:
        for location in my_pub.green_location_matches:
            location.scrape()

    # print "my_pub.base_matches", [(m.url, m.scrape_evidence) for m in my_pub.base_matches]

    return my_pub.green_location_matches




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

