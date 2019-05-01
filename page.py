#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import random
import re

import shortuuid
from sqlalchemy import sql
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import logger
from http_cache import http_get
from oa_local import find_normalized_license
from pdf_to_text import convert_pdf_to_txt
from oa_pmc import query_pmc
import oa_page
from util import is_pmc
from webpage import PmhRepoWebpage, PublisherWebpage


DEBUG_BASE = False


class PageNew(db.Model):
    id = db.Column(db.Text, primary_key=True)
    url = db.Column(db.Text)
    pmh_id = db.Column(db.Text, db.ForeignKey("pmh_record.id"))
    repo_id = db.Column(db.Text)  # delete once endpoint_id is populated
    endpoint_id = db.Column(db.Text, db.ForeignKey("endpoint.id"))
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

    endpoint = db.relationship(
        'Endpoint',
        lazy='subquery',
        uselist=None,
        viewonly=True
    )

    pmh_record = db.relationship(
        'PmhRecord',
        lazy='subquery',
        uselist=None,
        viewonly=True
    )

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
        return self.url and is_pmc(self.url)

    @property
    def pmcid(self):
        if not self.is_pmc:
            return None
        matches = re.findall(u"(pmc\d+)", self.url, re.IGNORECASE)
        if not matches:
            return None
        return matches[0].lower()

    def get_pmh_record_url(self):
        response = u"{}?verb=GetRecord&metadataPrefix=oai_dc&identifier={}".format(self.endpoint.pmh_url, self.pmh_id)
        return response

    # overwritten by subclasses
    def query_for_num_pub_matches(self):
        pass

    def scrape_eligible(self):
        return (
            (self.error is None or self.error == "") and
            (self.pmh_id and "oai:open-archive.highwire.org" not in self.pmh_id) and
            (self.url
                and 'zenodo.org' not in self.url
                and 'qmro.qmul.ac.uk' not in self.url)
        )

    def scrape_if_matches_pub(self):
        self.num_pub_matches = self.query_for_num_pub_matches()

        if self.num_pub_matches > 0 and self.scrape_eligible():
            return self.scrape()

    def enqueue_scrape_if_matches_pub(self):
        self.num_pub_matches = self.query_for_num_pub_matches()

        if self.num_pub_matches > 0 and self.scrape_eligible():
            stmt = sql.text(
                u'insert into page_green_scrape_queue (id, finished) values (:id, :finished) on conflict do nothing'
            ).bindparams(id=self.id, finished=self.scrape_updated)
            db.session.execute(stmt)

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
        if not self.scrape_eligible():
            logger.info('refusing to scrape this page')
            return

        self.updated = datetime.datetime.utcnow().isoformat()
        self.scrape_updated = datetime.datetime.utcnow().isoformat()
        self.scrape_pdf_url = None
        self.scrape_metadata_url = None
        self.scrape_license = None
        self.scrape_version = None
        self.error = ""

        if self.pmh_id != oa_page.oa_publisher_equivalent:
            self.scrape_green()
        else:
            self.scrape_publisher_equivalent()

    def scrape_publisher_equivalent(self):
        with PublisherWebpage(url=self.url) as publisher_page:
            publisher_page.scrape_for_fulltext_link()

            if publisher_page.is_open:
                self.scrape_version = publisher_page.open_version_source_string
                self.scrape_pdf_url = publisher_page.scraped_pdf_url
                self.scrape_metadata_url = publisher_page.scraped_open_metadata_url
                self.scrape_license = publisher_page.scraped_license
                if publisher_page.is_open and not publisher_page.scraped_pdf_url:
                    self.scrape_metadata_url = self.url

    def scrape_green(self):
        # handle these special cases, where we compute the pdf rather than looking for it
        if "oai:arXiv.org" in self.pmh_id:
            self.scrape_metadata_url = self.url
            self.scrape_pdf_url = self.url.replace("abs", "pdf")

        if self.is_pmc:
            self.set_info_for_pmc_page()

        if not self.scrape_pdf_url or not self.scrape_version:
            with PmhRepoWebpage(url=self.url, scraped_pdf_url=self.scrape_pdf_url, repo_id=self.repo_id) as my_webpage:
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
                    self.set_version_and_license(r=my_webpage.r)

        if self.scrape_pdf_url and not self.scrape_version:
            with PmhRepoWebpage(url=self.url, scraped_pdf_url=self.scrape_pdf_url, repo_id=self.repo_id) as my_webpage:
                my_webpage.set_r_for_pdf()
                self.set_version_and_license(r=my_webpage.r)

    def update_with_local_info(self):
        scrape_version_old = self.scrape_version
        scrape_license_old = self.scrape_license

        # if this repo has told us they will never have submitted, set default to be accepted
        if self.endpoint and self.endpoint.policy_promises_no_submitted:
            self.scrape_version = "acceptedVersion"

        # now look at the pmh record
        if self.pmh_record:
            # trust accepted in a variety of formats
            accepted_patterns = [
                re.compile(ur"accepted.?version", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"version.?accepted", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"accepted.?manuscript", re.IGNORECASE | re.MULTILINE | re.DOTALL)
                ]
            for pattern in accepted_patterns:
                if pattern.findall(self.pmh_record.api_raw):
                    self.scrape_version = "acceptedVersion"
            # print u"version for is {}".format(self.scrape_version)

            # trust a strict version of published version
            published_patterns = [
                re.compile(ur"<dc:type>.*publishedVersion</dc:type>", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"<free_to_read>.*published.*</free_to_read>", re.IGNORECASE | re.MULTILINE | re.DOTALL)
            ]
            for published_pattern in published_patterns:
                if published_pattern.findall(self.pmh_record.api_raw):
                    self.scrape_version = "publishedVersion"

            # get license if it is in pmh record
            rights_pattern = re.compile(ur"<dc:rights>(.*)</dc:rights>", re.IGNORECASE | re.MULTILINE | re.DOTALL)
            rights_matches = rights_pattern.findall(self.pmh_record.api_raw)
            for rights_text in rights_matches:
                open_license = find_normalized_license(rights_text)
                # only overwrite it if there is one, so doesn't overwrite anything scraped
                if open_license:
                    self.scrape_license = open_license

        if scrape_version_old != self.scrape_version or scrape_license_old != self.scrape_license:
            self.updated = datetime.datetime.utcnow().isoformat()
            print u"based on OAI-PMH metadata, updated {} {} for {} {}".format(self.scrape_version, self.scrape_license, self.url, self.id)
            return True

        # print u"based on metadata, assuming {} {} for {} {}".format(self.scrape_version, self.scrape_license, self.url, self.id)

        return False

    # use standards from https://wiki.surfnet.nl/display/DRIVERguidelines/Version+vocabulary
    # submittedVersion, acceptedVersion, publishedVersion
    def set_version_and_license(self, r=None):
        self.updated = datetime.datetime.utcnow().isoformat()

        if self.is_pmc:
            self.set_info_for_pmc_page()
            return

        # set as default
        self.scrape_version = "submittedVersion"

        is_updated = self.update_with_local_info()

        # now try to see what we can get out of the pdf itself

        if not r:
            logger.info(u"before scrape returning {} with scrape_version: {}, license {}".format(self.url, self.scrape_version, self.scrape_license))
            return

        try:
            # http://crossmark.dyndns.org/dialog/?doi=10.1016/j.jml.2012 at http://dspace.mit.edu/bitstream/1721.1/102417/1/Gibson_The%20syntactic.pdf
            if re.findall(u"crossmark\.[^/]*\.org/", r.content_big(), re.IGNORECASE):
                self.scrape_version = "publishedVersion"

            text = convert_pdf_to_txt(r, max_pages=25)

            # logger.info(text)

            if text and self.scrape_version == "submittedVersion":
                patterns = [
                    re.compile(ur"©.?\d{4}", re.UNICODE),
                    re.compile(ur"\(C\).?\d{4}", re.IGNORECASE),
                    re.compile(ur"copyright.{0,6}\d{4}", re.IGNORECASE),
                    re.compile(ur"received.{0,100}revised.{0,100}accepted.{0,100}publication", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur"all rights reserved", re.IGNORECASE),
                    re.compile(ur"This article is distributed under the terms of the Creative Commons", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur"This article is licensed under a Creative Commons", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur"this is an open access article", re.IGNORECASE | re.MULTILINE | re.DOTALL)
                    ]

                for pattern in patterns:
                    if pattern.findall(text):
                        logger.info(u'found {}, decided PDF is published version'.format(pattern.pattern))
                        self.scrape_version = "publishedVersion"

            if not self.scrape_license:
                open_license = find_normalized_license(text)
                if open_license:
                    logger.info(u'found license in PDF: {}'.format(open_license))
                    self.scrape_license = open_license

        except Exception as e:
            logger.exception(u"exception in convert_pdf_to_txt for {}".format(self.url))
            self.error += u"Exception doing convert_pdf_to_txt!"
            logger.info(self.error)

        logger.info(u"scrape returning {} with scrape_version: {}, license {}".format(self.url, self.scrape_version, self.scrape_license))

    def __repr__(self):
        return u"<PageNew ( {} ) {}>".format(self.pmh_id, self.url)

    def to_dict(self, include_id=True):
        response = {
            "oaipmh_id": self.pmh_id,
            "oaipmh_record_timestamp": self.record_timestamp.isoformat(),
            "pdf_url": self.scrape_pdf_url,
            "title": self.title,
            "version": self.scrape_version,
            "license": self.scrape_license,
            "oaipmh_api_url": self.get_pmh_record_url()
        }
        if include_id:
            response["id"] = self.id
        return response


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
    def endpoint_id(self):
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

    def update_with_local_info(self):
        pass

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





