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


class PmhVersionFirstAvailable(db.Model):
    endpoint_id = db.Column(db.Text, primary_key=True)
    pmh_id = db.Column(db.Text, primary_key=True)
    scrape_version = db.Column(db.Text, primary_key=True)
    first_available = db.Column(db.DateTime)
    url = db.Column(db.Text)


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

    rand = db.Column(db.Numeric)

    match_type = db.Column(db.Text)

    endpoint = db.relationship(
        'Endpoint',
        lazy='subquery',
        uselist=None,
        cascade="",
        viewonly=True
    )

    pmh_record = db.relationship(
        'PmhRecord',
        lazy='subquery',
        uselist=None,
        cascade="",
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
    def first_available(self):
        if self.pmh_record:
            lookup = PmhVersionFirstAvailable.query.filter(
                PmhVersionFirstAvailable.pmh_id == self.pmh_record.bare_pmh_id,
                PmhVersionFirstAvailable.endpoint_id == self.pmh_record.endpoint_id,
                PmhVersionFirstAvailable.scrape_version == self.scrape_version
            ).first()

            if lookup:
                return lookup.first_available.date()

        return self.save_first_version_availability()

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
        return self.endpoint and self.pmh_record and u"{}?verb=GetRecord&metadataPrefix={}&identifier={}".format(
            self.endpoint.pmh_url, self.endpoint.metadata_prefix, self.pmh_record.bare_pmh_id
        )

    @property
    def repository_display_name(self):
        if self.endpoint and self.endpoint.repo:
            return self.endpoint.repo.display_name()
        else:
            return None

    @property
    def bare_pmh_id(self):
        return self.pmh_record and self.pmh_record.bare_pmh_id

    # overwritten by subclasses
    def query_for_num_pub_matches(self):
        pass

    @property
    def has_no_error(self):
        return self.error is None or self.error == ""

    @property
    def scrape_updated_datetime(self):
        if isinstance(self.scrape_updated, basestring):
            return datetime.datetime.strptime(self.scrape_updated, "%Y-%m-%dT%H:%M:%S.%f")
        elif isinstance(self.scrape_updated, datetime.datetime):
            return self.scrape_updated
        else:
            return None

    def not_scraped_in(self, interval):
        return (
            not self.scrape_updated_datetime
            or self.scrape_updated_datetime < (datetime.datetime.now() - interval)
        )

    def scrape_eligible(self):
        return (
            (self.has_no_error or self.not_scraped_in(datetime.timedelta(weeks=1))) and
            (self.pmh_id and "oai:open-archive.highwire.org" not in self.pmh_id)
        )

    def scrape_if_matches_pub(self):
        self.num_pub_matches = self.query_for_num_pub_matches()

        if self.num_pub_matches > 0 and self.scrape_eligible():
            return self.scrape()

    def enqueue_scrape_if_matches_pub(self):
        self.num_pub_matches = self.query_for_num_pub_matches()

        if self.num_pub_matches > 0 and self.scrape_eligible():
            stmt = sql.text(
                u'insert into page_green_scrape_queue (id, finished, endpoint_id) values (:id, :finished, :endpoint_id) on conflict do nothing'
            ).bindparams(id=self.id, finished=self.scrape_updated, endpoint_id=self.endpoint_id)
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

        if self.pmh_id != oa_page.publisher_equivalent_pmh_id:
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
            return

        # https://ink.library.smu.edu.sg/do/oai/
        if self.endpoint and self.endpoint.id == 'ys9xnlw27yogrfsecedx' and u'ink.library.smu.edu.sg' in self.url:
            if u'viewcontent.cgi?' in self.url:
                return
            if self.pmh_record and find_normalized_license(self.pmh_record.license):
                self.scrape_metadata_url = self.url
                self.set_version_and_license()
                return

        if not self.scrape_pdf_url or not self.scrape_version:
            with PmhRepoWebpage(url=self.url, scraped_pdf_url=self.scrape_pdf_url, repo_id=self.repo_id) as my_webpage:
                if not self.scrape_pdf_url:
                    my_webpage.scrape_for_fulltext_link()
                    self.error += my_webpage.error
                    if my_webpage.is_open:
                        logger.info(u"** found an open copy! {}".format(my_webpage.fulltext_url))
                        self.scrape_updated = datetime.datetime.utcnow().isoformat()
                        self.scrape_metadata_url = self.url
                        if my_webpage.scraped_pdf_url:
                            self.scrape_pdf_url = my_webpage.scraped_pdf_url
                        if my_webpage.scraped_open_metadata_url:
                            self.scrape_metadata_url = my_webpage.scraped_open_metadata_url
                        if my_webpage.scraped_license:
                            self.scrape_license = my_webpage.scraped_license
                        if my_webpage.scraped_version:
                            self.scrape_version = my_webpage.scraped_version
                if self.scrape_pdf_url and not self.scrape_version:
                    self.set_version_and_license(r=my_webpage.r)

        if self.scrape_pdf_url and not self.scrape_version:
            with PmhRepoWebpage(url=self.url, scraped_pdf_url=self.scrape_pdf_url, repo_id=self.repo_id) as my_webpage:
                my_webpage.set_r_for_pdf()
                self.set_version_and_license(r=my_webpage.r)

        if self.is_open and not self.scrape_version:
            self.scrape_version = self.default_version()

        # associate certain landing page URLs with PDFs
        # https://repository.uantwerpen.be
        if self.endpoint and self.endpoint.id == 'mmv3envg3kaaztya9tmo':
            if self.scrape_pdf_url and self.scrape_pdf_url == self.scrape_metadata_url and self.pmh_record:
                logger.info(u'looking for landing page for {}'.format(self.scrape_pdf_url))
                landing_urls = [u for u in self.pmh_record.urls if u'hdl.handle.net' in u]
                if len(landing_urls) == 1:
                    logger.info(u'trying landing page {}'.format(landing_urls[0]))

                    try:
                        if http_get(landing_urls[0]).status_code == 200:
                            self.scrape_metadata_url = landing_urls[0]
                    except:
                        pass

                    if self.scrape_metadata_url:
                        logger.info(u'set landing page {}'.format(self.scrape_metadata_url))

    def pmc_first_available_date(self):
        if self.pmcid:
            pmc_result_list = query_pmc(self.pmcid)
            if pmc_result_list:
                pmc_result = pmc_result_list[0]
                received_date = pmc_result.get("fullTextReceivedDate", None)
                if received_date:
                    try:
                        return datetime.datetime.strptime(received_date, '%Y-%m-%d').date()
                    except Exception:
                        return None

        return None

    def save_first_version_availability(self):
        first_available = self.record_timestamp and self.record_timestamp.date()

        if self.pmcid and self.scrape_version:
            first_available = self.pmc_first_available_date()

        if (self.endpoint and self.endpoint.id and
                self.pmh_record and self.pmh_record.bare_pmh_id and
                self.url and
                self.scrape_version and
                first_available):
            stmt = sql.text(u'''
                insert into pmh_version_first_available
                (endpoint_id, pmh_id, url, scrape_version, first_available) values
                (:endpoint_id, :pmh_id, :url, :scrape_version, :first_available)
                on conflict do nothing
            ''').bindparams(
                endpoint_id=self.endpoint.id,
                pmh_id=self.pmh_record.bare_pmh_id,
                url=self.url,
                scrape_version=self.scrape_version,
                first_available=first_available
            )
            db.session.execute(stmt)

        return first_available

    def default_version(self):
        if self.endpoint and self.endpoint.policy_promises_no_submitted:
            return "acceptedVersion"
        else:
            return "submittedVersion"

    def update_with_local_info(self):
        scrape_version_old = self.scrape_version
        scrape_license_old = self.scrape_license

        # if this repo has told us they will never have submitted, set default to be accepted
        if self.endpoint and self.endpoint.policy_promises_no_submitted and self.scrape_version != "publishedVersion":
            self.scrape_version = "acceptedVersion"

        # now look at the pmh record
        if self.pmh_record:
            # trust accepted in a variety of formats
            accepted_patterns = [
                re.compile(ur"accepted.?version", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"version.?accepted", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"accepted.?manuscript", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"<dc:type>peer.?reviewed</dc:type>", re.IGNORECASE | re.MULTILINE | re.DOTALL)
                ]
            for pattern in accepted_patterns:
                if pattern.findall(self.pmh_record.api_raw):
                    self.scrape_version = "acceptedVersion"
            # print u"version for is {}".format(self.scrape_version)

            # trust a strict version of published version
            published_patterns = [
                re.compile(ur"<dc:type>.*publishedVersion</dc:type>", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"<dc:type\.version>.*publishedVersion</dc:type\.version>", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                re.compile(ur"<free_to_read>.*published.*</free_to_read>", re.IGNORECASE | re.MULTILINE | re.DOTALL)
            ]
            for published_pattern in published_patterns:
                if published_pattern.findall(self.pmh_record.api_raw):
                    self.scrape_version = "publishedVersion"

            # get license if it is in pmh record
            rights_pattern = re.compile(ur"<dc:rights>(.*)</dc:rights>", re.IGNORECASE | re.MULTILINE | re.DOTALL)
            rights_matches = rights_pattern.findall(self.pmh_record.api_raw)
            rights_license_pattern = re.compile(ur"<dc:rights\.license>(.*)</dc:rights\.license>", re.IGNORECASE | re.MULTILINE | re.DOTALL)
            rights_matches.extend(rights_license_pattern.findall(self.pmh_record.api_raw))

            for rights_text in rights_matches:
                open_license = find_normalized_license(rights_text)
                # only overwrite it if there is one, so doesn't overwrite anything scraped
                if open_license:
                    self.scrape_license = open_license

            self.scrape_version = _scrape_version_override().get(self.pmh_record.pmh_id, self.scrape_version)

        if self.scrape_pdf_url and re.search(ur'^https?://rke\.abertay\.ac\.uk', self.scrape_pdf_url):
            if re.search(ur'Publishe[dr]_?\d\d\d\d\.pdf$', self.scrape_pdf_url):
                self.scrape_version = "publishedVersion"
            if re.search(ur'\d\d\d\d_?Publishe[dr].pdf$', self.scrape_pdf_url):
                self.scrape_version = "publishedVersion"

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
        self.scrape_version = self.default_version()

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

            if text and self.scrape_version != "publishedVersion":
                patterns = [
                    re.compile(ur"©.?\d{4}", re.UNICODE),
                    re.compile(ur"\(C\).?\d{4}", re.IGNORECASE),
                    re.compile(ur"copyright.{0,6}\d{4}", re.IGNORECASE),
                    re.compile(ur"received.{0,100}revised.{0,100}accepted.{0,100}publication", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur"all rights reserved", re.IGNORECASE),
                    re.compile(ur"This article is distributed under the terms of the Creative Commons", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur"This article is licensed under a Creative Commons", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur"this is an open access article", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur"This article is brought to you for free and open access by Works.", re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    ]

                for pattern in patterns:
                    if pattern.findall(text):
                        logger.info(u'found {}, decided PDF is published version'.format(pattern.pattern))
                        self.scrape_version = "publishedVersion"

            if text and self.scrape_version != 'acceptedVersion':
                patterns = [
                    re.compile(ur'This is a post-peer-review, pre-copyedit version', re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur'This is the peer reviewed version of the following article', re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur'The present manuscript as of \d\d \w+ \d\d\d\d has been accepted', re.IGNORECASE | re.MULTILINE | re.DOTALL),
                    re.compile(ur'Post-peer-review, pre-copyedit version of accepted manuscript', re.IGNORECASE | re.MULTILINE | re.DOTALL),
                ]

                for pattern in patterns:
                    if pattern.findall(text):
                        logger.info(u'found {}, decided PDF is accepted version'.format(pattern.pattern))
                        self.scrape_version = "acceptedVersion"

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
            "oaipmh_id": self.pmh_record and self.pmh_record.bare_pmh_id,
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
    # https://github.com/pallets/flask-sqlalchemy/issues/492
    __tablename__ = None

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
    # https://github.com/pallets/flask-sqlalchemy/issues/492
    __tablename__ = None

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
    def first_available(self):
        return None

    @property
    def pmh_id(self):
        return self.id

    @property
    def bare_pmh_id(self):
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

    @property
    def repository_display_name(self):
        return self.repo_id

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


def _scrape_version_override():
    return {
        'oai:dspace.cvut.cz:10467/86163': 'submittedVersion',
        'oai:repository.arizona.edu:10150/633848': 'acceptedVersion',
        'oai:archive.ugent.be:6914822': 'acceptedVersion',
        'oai:serval.unil.ch:BIB_E033703283B2': 'acceptedVersion',
        'oai:serval.unil.ch:BIB_3108959306C9': 'acceptedVersion',
        'oai:serval.unil.ch:BIB_08C9BAB31C2E': 'acceptedVersion',
        'oai:serval.unil.ch:BIB_E8CC2511C152': 'acceptedVersion',
        'oai:HAL:hal-01924005v1': 'acceptedVersion',
    }
