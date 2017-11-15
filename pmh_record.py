#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import datetime
from time import time
from HTMLParser import HTMLParser
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import logger
from page import Page
from page import PageNew
from page import PageDoiMatch
from page import PageTitleMatch
from util import normalize_title


DEBUG_BASE = False

def title_is_too_short(normalized_title):
    if not normalized_title:
        return True
    return len(normalized_title) <= 21

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

    pages = db.relationship(
        # 'Page',
        'PageNew',
        lazy='subquery',
        cascade="all, delete-orphan",
        # don't want a backref because don't want page to link to this
        # backref=db.backref("pmh_record", lazy="subquery"),
        # foreign_keys="Page.id"
        foreign_keys="PageNew.pmh_id"
    )

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


    def mint_page_for_url(self, page_class, url):
        my_page = page_class()
        my_page.pmh_id = self.id
        my_page.url = url
        my_page.doi = self.doi
        my_page.title = self.title
        my_page.normalized_title = normalize_title(self.title)
        my_page.authors = self.authors
        my_page.repo_id = self.id.split(":")[1]
        return my_page


    def mint_pages(self):
        if u"oai:" not in self.id:
            return

        self.pages = []

        for url in self.get_good_urls():
            if self.doi:
                my_page = self.mint_page_for_url(PageDoiMatch, url)
                self.pages.append(my_page)

            if self.title:
                normalized_title = normalize_title(self.title)
                if normalized_title:
                    my_page = self.mint_page_for_url(PageTitleMatch, url)
                    pages_with_this_normalized_title = PageTitleMatch.query.filter(PageTitleMatch.normalized_title==normalized_title).all()
                    if len(pages_with_this_normalized_title) >= 20:
                        my_page.more_than_20 = True
                    self.pages.append(my_page)

        return self.pages


    def __repr__(self):
        return u"<PmhRecord ({}) doi:{} '{}...'>".format(self.id, self.doi, self.title[0:20])


