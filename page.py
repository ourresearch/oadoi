#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import datetime
from sqlalchemy import sql
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import logger
from webpage import WebpageInPmhRepo
from oa_local import find_normalized_license
from oa_pdf import convert_pdf_to_txt
from util import remove_punctuation
from util import get_sql_answer
from util import is_the_same_url

DEBUG_BASE = False

def compute_normalized_title(title):
    normalized_title = get_sql_answer(db, u"select normalize_title_v2('{}')".format(remove_punctuation(title)))
    return normalized_title


def is_pmcid_published_version(pmcid):
    q = u"""select published_version from pmcid_lookup where pmcid = '{}'""".format(pmcid)
    row = db.engine.execute(sql.text(q)).first()
    if not row:
        return False
    return row[0] == True


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
    def is_open(self):
        return self.scrape_metadata_url or self.scrape_pdf_url

    def scrape(self):
        self.updated = datetime.datetime.utcnow().isoformat()
        self.scrape_updated = datetime.datetime.utcnow().isoformat()
        self.scrape_pdf_url = None
        self.scrape_metadata_url = None
        self.scrape_license = None
        self.scrape_version = None

        # handle these special cases, where we compute the pdf rather than looking for it
        if "oai:pubmedcentral.nih.gov" in self.id:
            self.scrape_metadata_url = self.url
            self.scrape_pdf_url = u"{}/pdf".format(self.url)
        if "oai:arXiv.org" in self.id:
            self.scrape_metadata_url = self.url
            self.scrape_pdf_url = self.url.replace("abs", "pdf")

        # delete this part at some point once we've done all the old matches we want to do
        if not self.scrape_pdf_url:
            base_matches = BaseMatch.query.filter(or_(BaseMatch.url==self.url,
                                                       BaseMatch.scrape_metadata_url==self.url,
                                                       BaseMatch.scrape_pdf_url==self.url)).all()
            if base_matches:
                logger.info(u"** found base match version")
                for base_match in base_matches:
                    self.scrape_updated = base_match.scrape_updated
                    self.scrape_pdf_url = base_match.scrape_pdf_url
                    self.scrape_metadata_url = base_match.scrape_metadata_url
                    self.scrape_license = base_match.scrape_license
                    self.scrape_version = base_match.scrape_version
            else:
                logger.info(u"did not find a base match version")

        my_webpage = WebpageInPmhRepo(url=self.url, scraped_pdf_url=self.scrape_pdf_url)
        if not self.scrape_pdf_url:
            my_webpage.scrape_for_fulltext_link()
            if my_webpage.is_open:
                self.scrape_updated = datetime.datetime.utcnow().isoformat()
                self.metadata_url = self.url
                logger.info(u"** found an open copy! {}".format(my_webpage.fulltext_url))
                self.scrape_pdf_url = my_webpage.scraped_pdf_url
                self.scrape_metadata_url = my_webpage.scraped_open_metadata_url
                self.scrape_license = my_webpage.scraped_license

        if self.scrape_pdf_url and not self.scrape_version:
            if my_webpage and my_webpage.r:
                history_urls = [h.url for h in my_webpage.r.history]
                if not any([is_the_same_url(url, self.scrape_pdf_url) for url in history_urls]):
                    logger.info(u"don't have the pdf, so getting it to get the version")
                    my_webpage.set_r_for_pdf()
            self.set_version_and_license(r=my_webpage.r)


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


    # use standards from https://wiki.surfnet.nl/display/DRIVERguidelines/Version+vocabulary
    # submittedVersion, acceptedVersion, publishedVersion
    def set_version_and_license(self, r=None):

        # set as default
        self.scrape_version = "submittedVersion"

        if self.is_pmc:
            if is_pmcid_published_version(self.pmcid):
                self.scrape_version = "publishedVersion"
            else:
                self.scrape_version = "acceptedVersion"
            return

        if r:
            try:
                text = convert_pdf_to_txt(r)
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
                            self.scrape_version = "publishedVersion"

                    logger.info(u"returning with scrape_version={}".format(self.scrape_version))

                    open_license = find_normalized_license(text)
                    if open_license:
                        self.scrape_license = open_license

            except Exception as e:
                self.error += u"Exception doing convert_pdf_to_txt on {}! investigate! {}".format(self.scrape_pdf_url, unicode(e.message).encode("utf-8"))
                logger.info(self.error)
                pass



    def __repr__(self):
        return u"<Page ( {} ) {} doi:{} '{}...'>".format(self.id, self.url, self.doi, self.title[0:20])



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





