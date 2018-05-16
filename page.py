#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import datetime
from sqlalchemy import sql
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import JSONB
import random
import requests
import shortuuid

from app import db
from app import logger
from webpage import WebpageInPmhRepo
# from pmh_record import PmhRecord

from oa_local import find_normalized_license
from oa_pdf import convert_pdf_to_txt
from oa_pmc import query_pmc
from http_cache import http_get
from util import remove_punctuation
from util import get_sql_answer
from util import is_the_same_url
from util import normalize_title


DEBUG_BASE = False


class PageNew(db.Model):
    id = db.Column(db.Text, primary_key=True)
    url = db.Column(db.Text)
    pmh_id = db.Column(db.Text, db.ForeignKey("pmh_record.id"))
    repo_id = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey("pub.id"))
    title = db.Column(db.Text)
    normalized_title = db.Column(db.Text, db.ForeignKey("pub.normalized_title"))
    authors = db.Column(JSONB)
    record_timestamp = db.Column(db.DateTime)

    scrape_updated = db.Column(db.DateTime)
    scrape_pdf_url = db.Column(db.Text)
    scrape_metadata_url = db.Column(db.Text)
    scrape_version = db.Column(db.Text)
    scrape_license = db.Column(db.Text)
    num_pub_matches = db.Column(db.Numeric)

    error = db.Column(db.Text)
    updated = db.Column(db.DateTime)

    started = db.Column(db.DateTime)
    finished = db.Column(db.DateTime)
    rand = db.Column(db.Numeric)

    match_type = db.Column(db.Text)

    __mapper_args__ = {
        "polymorphic_on": match_type,
        "polymorphic_identity": "page_new"
    }

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:20]
        self.error = ""
        self.rand = random.random()
        self.updated = datetime.datetime.utcnow().isoformat()
        super(PageNew, self).__init__(**kwargs)

    @property
    def is_open(self):
        return self.scrape_metadata_url or self.scrape_pdf_url

    @property
    def is_pmc(self):
        if not self.url:
            return False
        if u"ncbi.nlm.nih.gov/pmc" in self.url:
            return True
        if u"europepmc.org/articles/" in self.url:
            return True
        return False

    @property
    def pmcid(self):
        if not self.is_pmc:
            return None
        matches = re.findall(u"(pmc\d+)", self.url, re.IGNORECASE)
        if not matches:
            return None
        return matches[0].lower()

    # overwritten by subclasses
    def query_for_num_pub_matches(self):
        pass

    def scrape_if_matches_pub(self):
        # if self.scrape_updated:
        #     logger.info(u"already scraped, returning: {}".format(self))
        #     return

        self.num_pub_matches = self.query_for_num_pub_matches()

        if self.num_pub_matches > 0:
            return self.scrape()

    def set_info_for_pmc_page(self):
        if not self.pmcid:
            return

        result_list = query_pmc(self.pmcid)
        if not result_list:
            return
        result = result_list[0]
        has_pdf = result.get("hasPDF", None)
        is_author_manuscript = result.get("authMan", None)
        is_open_access = result.get("isOpenAccess", None)
        raw_license = result.get("license", None)

        self.scrape_metadata_url = u"http://europepmc.org/articles/{}".format(self.pmcid)
        if has_pdf == u"Y":
            self.scrape_pdf_url = u"http://europepmc.org/articles/{}?pdf=render".format(self.pmcid)
        if is_author_manuscript == u"Y":
            self.scrape_version = u"acceptedVersion"
        else:
            self.scrape_version = u"publishedVersion"
        if raw_license:
            self.scrape_license = find_normalized_license(raw_license)
        elif is_open_access == "Y":
            self.scrape_license = u"implied-oa"

        # except Exception as e:
        #     self.error += u"Exception in set_info_for_pmc_page"
        #     logger.info(u"Exception in set_info_for_pmc_page")


    def scrape(self):
        self.updated = datetime.datetime.utcnow().isoformat()
        self.scrape_updated = datetime.datetime.utcnow().isoformat()
        self.scrape_pdf_url = None
        self.scrape_metadata_url = None
        self.scrape_license = None
        self.scrape_version = None
        self.error = ""

        # handle these special cases, where we compute the pdf rather than looking for it
        if "oai:arXiv.org" in self.pmh_id:
            self.scrape_metadata_url = self.url
            self.scrape_pdf_url = self.url.replace("abs", "pdf")
        if self.is_pmc:
            self.set_info_for_pmc_page()

        # delete this part at some point once we've done all the old matches we want to do
        # if not self.scrape_pdf_url:
        #     base_matches = BaseMatch.query.filter(or_(BaseMatch.url==self.url,
        #                                                BaseMatch.scrape_metadata_url==self.url,
        #                                                BaseMatch.scrape_pdf_url==self.url)).all()
        #     if base_matches:
        #         logger.info(u"** found base match version")
        #         for base_match in base_matches:
        #             self.scrape_updated = base_match.scrape_updated
        #             self.scrape_pdf_url = base_match.scrape_pdf_url
        #             self.scrape_metadata_url = base_match.scrape_metadata_url
        #             self.scrape_license = base_match.scrape_license
        #             self.scrape_version = base_match.scrape_version
        #     else:
        #         logger.info(u"did not find a base match version")

        if not self.scrape_pdf_url or not self.scrape_version:
            my_webpage = WebpageInPmhRepo(url=self.url, scraped_pdf_url=self.scrape_pdf_url)
            if not self.scrape_pdf_url:
                my_webpage.scrape_for_fulltext_link()
                self.error += my_webpage.error
                if my_webpage.is_open:
                    logger.info(u"** found an open copy! {}".format(my_webpage.fulltext_url))
                    self.scrape_updated = datetime.datetime.utcnow().isoformat()
                    self.metadata_url = self.url
                    if my_webpage.scraped_pdf_url:
                        self.scrape_pdf_url = my_webpage.scraped_pdf_url
                    if my_webpage.scraped_open_metadata_url:
                        self.scrape_metadata_url = my_webpage.scraped_open_metadata_url
                    if my_webpage.scraped_license:
                        self.scrape_license = my_webpage.scraped_license

        if self.scrape_pdf_url and not self.scrape_version:
            have_the_pdf = False
            if my_webpage and my_webpage.r:
                history_urls = [my_webpage.r.url] + [h.url for h in my_webpage.r.history]
                if any([is_the_same_url(url, self.scrape_pdf_url) for url in history_urls]):
                    have_the_pdf = True
            if not have_the_pdf:
                logger.info(u"don't have the full pdf, so getting it to get the version")
                my_webpage.set_r_for_pdf()
            if my_webpage.r:
                self.set_version_and_license(r=my_webpage.r)


    # use standards from https://wiki.surfnet.nl/display/DRIVERguidelines/Version+vocabulary
    # submittedVersion, acceptedVersion, publishedVersion
    def set_version_and_license(self, r=None):

        if self.is_pmc:
            self.set_info_for_pmc_page()
            return

        # set as default
        self.scrape_version = "submittedVersion"

        if not r:
            return

        try:
            # http://crossmark.dyndns.org/dialog/?doi=10.1016/j.jml.2012 at http://dspace.mit.edu/bitstream/1721.1/102417/1/Gibson_The%20syntactic.pdf
            if re.findall(u"crossmark\.[^/]*\.org/", r.text, re.IGNORECASE):
                self.scrape_version = "publishedVersion"

            text = convert_pdf_to_txt(r)
            # logger.info(text)
            if text and self.scrape_version == "submittedVersion":
                patterns = [
                    re.compile(ur"©.?\d{4}", re.UNICODE),
                    re.compile(ur"\(C\).?\d{4}", re.IGNORECASE),
                    re.compile(ur"copyright \d{4}", re.IGNORECASE),
                    re.compile(ur"all rights reserved", re.IGNORECASE),
                    re.compile(ur"This article is distributed under the terms of the Creative Commons", re.IGNORECASE),
                    re.compile(ur"this is an open access article", re.IGNORECASE)
                    ]

                for pattern in patterns:
                    matches = pattern.findall(text)
                    if matches:
                        self.scrape_version = "publishedVersion"

            logger.info(u"returning {} with scrape_version: {}".format(self.url, self.scrape_version))

            open_license = find_normalized_license(text)
            if open_license:
                self.scrape_license = open_license

        except Exception as e:
            self.error += u"Exception doing convert_pdf_to_txt!"
            logger.info(self.error)
            pass


    def __repr__(self):
        return u"<PageNew ( {} ) {}>".format(self.pmh_id, self.url)


class PageDoiMatch(PageNew):
    __mapper_args__ = {
        "polymorphic_identity": "doi"
    }

    def query_for_num_pub_matches(self):
        from pub import Pub
        num_pubs_with_this_doi = db.session.query(Pub.id).filter(Pub.id==self.doi).count()
        return num_pubs_with_this_doi


    def __repr__(self):
        return u"<PageDoiMatch ( {} ) {} doi:{}>".format(self.pmh_id, self.url, self.doi)


class PageTitleMatch(PageNew):
    __mapper_args__ = {
        "polymorphic_identity": "title"
    }

    def query_for_num_pub_matches(self):
        from pmh_record import title_is_too_common
        from pmh_record import title_is_too_short
        from pub import Pub

        # it takes too long to query for things like "tablecontents"
        if title_is_too_common(self.normalized_title) or title_is_too_short(self.normalized_title):
            logger.info(u"title is too common or too short, not scraping")
            return -1

        num_pubs_with_this_normalized_title = db.session.query(Pub.id).filter(Pub.normalized_title==self.normalized_title).count()
        return num_pubs_with_this_normalized_title

    def __repr__(self):
        return u"<PageTitleMatch ( {} ) {} '{}...'>".format(self.pmh_id, self.url, self.title[0:20])


class Page(db.Model):
    url = db.Column(db.Text, primary_key=True)
    id = db.Column(db.Text, db.ForeignKey("pmh_record.id"))
    source = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey("pub.id"))
    title = db.Column(db.Text)
    normalized_title = db.Column(db.Text, db.ForeignKey("pub.normalized_title"))
    authors = db.Column(JSONB)

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
    def pmh_id(self):
        return self.id

    @property
    def is_open(self):
        return self.scrape_metadata_url or self.scrape_pdf_url

    @property
    def is_pmc(self):
        if not self.url:
            return False
        if u"ncbi.nlm.nih.gov/pmc" in self.url:
            return True
        if u"europepmc.org/articles/" in self.url:
            return True
        return False

    @property
    def repo_id(self):
        if not self.pmh_id or not ":" in self.pmh_id:
            return None
        return self.pmh_id.split(":")[1]


    @property
    def pmcid(self):
        if not self.is_pmc:
            return None
        return self.url.rsplit("/", 1)[1].lower()

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


    # examples
    # https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMC3039489&resulttype=core&format=json&tool=oadoi
    # https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMC3606428&resulttype=core&format=json&tool=oadoi
    def set_info_for_pmc_page(self):
        if not self.pmcid:
            return

        url_template = u"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={}&resulttype=core&format=json&tool=oadoi"
        url = url_template.format(self.pmcid)

        # try:
        r = http_get(url)
        data = r.json()
        result_list = data["resultList"]["result"]
        if not result_list:
            return
        result = result_list[0]
        has_pdf = result.get("hasPDF", None)
        is_author_manuscript = result.get("authMan", None)
        is_open_access = result.get("isOpenAccess", None)
        raw_license = result.get("license", None)

        self.scrape_metadata_url = u"http://europepmc.org/articles/{}".format(self.pmcid)
        if has_pdf == u"Y":
            self.scrape_pdf_url = u"http://europepmc.org/articles/{}?pdf=render".format(self.pmcid)
        if is_author_manuscript == u"Y":
            self.scrape_version = u"acceptedVersion"
        else:
            self.scrape_version = u"publishedVersion"
        if raw_license:
            self.scrape_license = find_normalized_license(raw_license)
        elif is_open_access == "Y":
            self.scrape_license = u"implied-oa"

        # except Exception as e:
        #     self.error += u"Exception in set_info_for_pmc_page"
        #     logger.info(u"Exception in set_info_for_pmc_page")


    def __repr__(self):
        return u"<Page ( {} ) {} doi:{} '{}...'>".format(self.pmh_id, self.url, self.doi, self.title[0:20])



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





