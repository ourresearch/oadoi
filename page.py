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
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property
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

def is_pmcid_author_version(pmcid):
    q = u"""select author_manuscript from pmcid_lookup where pmcid = '{}'""".format(pmcid)
    row = db.engine.execute(sql.text(q)).first()
    if not row:
        return False
    return row[0] == True




class Page(db.Model):
    url = db.Column(db.Text, primary_key=True)
    id = db.Column(db.Text, db.ForeignKey("pmh_record.id"))
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
            if not self.scrape_version:
                self.set_version_and_license(do_scrape=False)  #@todo fix this

        # do this for now, so things stay updated
        my_pub.run()
        db.session.merge(my_pub)

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
    def set_version_and_license(self, do_scrape=True):

        # set as default
        self.scrape_version = "submittedVersion"

        # if self.host_type == "publisher":
        #     return "publishedVersion"
        if self.is_preprint_repo:
            self.scrape_version = "submittedVersion"

        if self.is_pmc:
            if is_pmcid_author_version(self.pmcid):
                self.scrape_version = "acceptedVersion"
            else:
                self.scrape_version = "publishedVersion"

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
                            self.scrape_version = "publishedVersion"

                    open_license = find_normalized_license(text)
                    if open_license:
                        self.scrape_license = open_license
            except Exception as e:
                self.error += u"Exception doing convert_pdf_to_txt on {}! investigate! {}".format(self.scrape_pdf_url, unicode(e.message).encode("utf-8"))
                logger.info(self.error)
                pass



    def __repr__(self):
        return u"<Page ({}) {} doi:{} '{}'>".format(self.id, self.url, self.doi, self.title)


