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
from webpage import WebpageInBaseRepo
from webpage import WebpageInPmhRepo
from oa_local import find_normalized_license
from oa_pdf import convert_pdf_to_txt
from util import elapsed
from util import normalize
from util import remove_punctuation


DEBUG_BASE = False


class BaseResponseAddin():

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



    def make_green_locations(self, my_pub, match_type, do_scrape=True):
        green_locations = []

        for url in self.get_good_urls():
            my_green_location = GreenLocation()
            my_green_location.id = self.id
            my_green_location.url = url
            my_green_location.doi = my_pub.id
            my_green_location.scrape_evidence = u"oa repository (via OAI-PMH {} match)".format(match_type)
            green_locations.append(my_green_location)

        return green_locations


class PmhRecordMatchedByTitle(db.Model, BaseResponseAddin):
    id = db.Column(db.Text, db.ForeignKey('pmh_record.id'), primary_key=True)
    doi = db.Column(db.Text)
    title = db.Column(db.Text)
    normalized_title = db.Column(db.Text, db.ForeignKey('crossref_title_view.normalized_title'))
    urls = db.Column(JSONB)
    authors = db.Column(JSONB)
    relations = db.Column(JSONB)
    sources = db.Column(JSONB)


class GreenLocation(db.Model):
    id = db.Column(db.Text, primary_key=True)
    url = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'), primary_key=True)

    scrape_updated = db.Column(db.DateTime)
    scrape_evidence = db.Column(db.Text)
    scrape_pdf_url = db.Column(db.Text)
    scrape_metadata_url = db.Column(db.Text)
    scrape_version = db.Column(db.Text)
    scrape_license = db.Column(db.Text)

    error = db.Column(db.Text)
    updated = db.Column(db.DateTime)

    started = db.Column(db.DateTime)
    finished = db.Column(db.DateTime)
    rand = db.Column(db.Numeric)

    def __init__(self, **kwargs):
        self.error = ""
        self.updated = datetime.datetime.utcnow().isoformat()
        super(self.__class__, self).__init__(**kwargs)

    @property
    def is_open(self):
        return self.scrape_metadata_url or self.scrape_pdf_url

    def scrape(self):
        if self.scrape_pdf_url and self.scrape_version:
            return

        self.scrape_updated = datetime.datetime.utcnow().isoformat()
        self.updated = datetime.datetime.utcnow().isoformat()

        # handle these special cases, where we compute the pdf rather than looking for it
        if "oai:pubmedcentral.nih.gov" in self.id:
            self.scrape_metadata_url = self.url
            self.scrape_pdf_url = u"{}/pdf".format(self.url)
        if "oai:arXiv.org" in self.id:
            self.scrape_metadata_url = self.url
            self.scrape_pdf_url = self.url.replace("abs", "pdf")

        my_pub = self.crossref_by_doi
        if my_pub:
            for base_match in my_pub.base_matches:
                if self.url==base_match.scrape_metadata_url or self.url==base_match.scrape_pdf_url:
                    self.scrape_updated = base_match.scrape_updated
                    self.scrape_pdf_url = base_match.scrape_pdf_url
                    self.scrape_metadata_url = base_match.scrape_metadata_url
                    self.scrape_license = base_match.scrape_license
                    self.scrape_version = base_match.scrape_version

        if self.scrape_pdf_url and self.scrape_version:
            return

        my_webpage = WebpageInPmhRepo(url=self.url)
        my_webpage.scrape_for_fulltext_link()

        if my_webpage.is_open:
            self.scrape_updated = datetime.datetime.utcnow().isoformat()
            self.metadata_url = self.url
            logger.info(u"** found an open copy! {}".format(my_webpage.fulltext_url))
            # self.scrape_evidence = my_webpage.scrape_evidence
            self.scrape_pdf_url = my_webpage.scraped_pdf_url
            self.scrape_metadata_url = my_webpage.scraped_open_metadata_url
            self.scrape_license = my_webpage.scraped_license
            if self.scrape_pdf_url:
                self.scrape_version = self.find_version(do_scrape=True)

    @property
    def is_pmc(self):
        if not self.url:
            return False
        return "ncbi.nlm.nih.gov/pmc" in self.url

    @property
    def pmcid(self):
        if not self.is_pmc:
            return None
        return self.url.rsplit("/", 1)[1].lower()

    @property
    def is_pmc_author_manuscript(self):
        if not self.is_pmc:
            return False
        q = u"""select author_manuscript from pmcid_lookup where pmcid = '{}'""".format(self.pmcid)
        row = db.engine.execute(sql.text(q)).first()
        if not row:
            return False
        return row[0] == True

    @property
    def is_preprint_repo(self):
        preprint_url_fragments = [
            "precedings.nature.com",
            "10.15200/winn.",
            "/peerj.preprints",
            ".figshare.",
            "10.1101/",  #biorxiv
            "10.15363/" #thinklab
        ]
        for url_fragment in preprint_url_fragments:
            if self.url and url_fragment in self.url.lower():
                return True
        return False

    # use stanards from https://wiki.surfnet.nl/display/DRIVERguidelines/Version+vocabulary
    # submittedVersion, acceptedVersion, publishedVersion
    def find_version(self, do_scrape=True):
        # if self.host_type == "publisher":
        #     return "publishedVersion"
        if self.is_preprint_repo:
            return "submittedVersion"
        if self.is_pmc:
            if self.is_pmc_author_manuscript:
                return "acceptedVersion"
            else:
                return "publishedVersion"

        if do_scrape and self.scrape_pdf_url:
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
                            logger.info(u"found publishedVersion via scrape!")
                            return "publishedVersion"
            except Exception as e:
                self.error += u"Exception doing convert_pdf_to_txt on {}! investigate! {}".format(self.scrape_pdf_url, unicode(e.message).encode("utf-8"))
                logger.info(self.error)
                pass

        return "submittedVersion"

    def __repr__(self):
        return u"<GreenLocation ({} {} {})>".format(self.id, self.doi, self.url)


class PmhRecord(db.Model, BaseResponseAddin):
    id = db.Column(db.Text, primary_key=True)
    source = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'))
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

    def __init__(self, **kwargs):
        self.updated = datetime.datetime.utcnow().isoformat()
        super(self.__class__, self).__init__(**kwargs)

    def __repr__(self):
        return u"<PmhRecord ({})>".format(self.id)


# legacy, just used for matching
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
        green_locations += pmh_record_obj.make_green_locations(my_pub, match_type, do_scrape=do_scrape)

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
            green_locations += pmh_record_title_obj.make_green_locations(my_pub, match_type, do_scrape=do_scrape)

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

