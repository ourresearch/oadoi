from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred
from sqlalchemy import or_

from time import time
from time import sleep
from random import random
import datetime
from contextlib import closing
from lxml import etree
from threading import Thread
import logging
import requests
import shortuuid
import os

from app import db

from util import elapsed
from util import clean_doi
from util import safe_commit
import oa_local
import oa_scrape
import oa_base
from version import Version
from version import version_sort_score


def call_targets_in_parallel(targets):
    # print u"calling", targets
    threads = []
    for target in targets:
        process = Thread(target=target, args=[])
        process.start()
        threads.append(process)
    for process in threads:
        process.join(timeout=10)
    # print u"finished the calls to", targets

def call_args_in_parallel(target, args_list):
    # print u"calling", targets
    threads = []
    for args in args_list:
        process = Thread(target=target, args=args)
        process.start()
        threads.append(process)
    for process in threads:
        process.join(timeout=10)
    # print u"finished the calls to", targets


def get_pub_from_doi(doi, force_refresh=False):
    my_pub = Publication.query.filter_by(doi=doi).first()
    if my_pub:
        print u"found pub {} in db".format(my_pub)
    else:
        my_pub = build_product(**{"doi": doi})

    if force_refresh or not my_pub.evidence:
        my_pub.clear_versions()
        my_pub.find_open_versions()
        my_pub.updated = datetime.datetime.utcnow()
        db.session.merge(my_pub)
        safe_commit(db)
        print u"update db with pub"

    return my_pub


def run_collection_from_biblio(use_cache, **biblio):
    my_product = build_product(**biblio)
    my_product.find_open_versions()
    return my_product


def lookup_product_in_db(**request_kwargs):
    q = Product.query
    if "doi" in request_kwargs:
        q = q.filter(Product.doi==request_kwargs["doi"])
    elif "url" in request_kwargs:
        if "title" in request_kwargs:
            q = q.filter(or_(Product.title==request_kwargs["title"], Product.url==request_kwargs["url"]))
        else:
            q = q.filter(Product.url==request_kwargs["url"])
    my_product = q.first()
    if my_product:
        print u"found {} in cache!".format(my_product.url)

    return my_product


def build_product(**request_kwargs):
    my_product = None
    my_product = Publication(**request_kwargs)
    return my_product









class Publication(db.Model):
    id = db.Column(db.Text, primary_key=True)

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    doi = db.Column(db.Text)
    url = db.Column(db.Text)
    title = db.Column(db.Text)

    fulltext_url = db.Column(db.Text)
    license = db.Column(db.Text)
    evidence = db.Column(db.Text)

    crossref_api_raw = deferred(db.Column(JSONB))
    error = db.Column(db.Text)
    error_message = db.Column(db.Text)

    versions = db.relationship(
        'Version',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("publication", lazy="subquery"),
        foreign_keys="Version.pub_id"
    )

    def __init__(self, **kwargs):
        self.request_kwargs = kwargs
        self.base_dcoa = None
        self.repo_urls = {"urls": []}
        self.license_string = ""
        self.product_id = None
        self.key = None

        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow()
        self.updated = datetime.datetime.utcnow()

        for (k, v) in kwargs.iteritems():
            if v:
                value = v.strip()
                setattr(self, k, value)

        if self.doi:
            self.doi = clean_doi(self.doi)
            self.url = u"http://doi.org/{}".format(self.doi)


    @property
    def best_redirect_url(self):
        if self.fulltext_url:
            return self.fulltext_url
        else:
            return self.url

    @property
    def has_fulltext_url(self):
        return (self.fulltext_url != None)

    @property
    def has_license(self):
        if not self.license:
            return False
        if self.license == "unknown":
            return False
        return True

    @property
    def clean_doi(self):
        if not self.doi:
            return None
        return clean_doi(self.doi)


    def decide_if_open(self):
        # look through the versions here

        sorted_versions = sorted(self.versions, key=lambda x:version_sort_score(x), reverse=True)

        # overwrites, hence the sorting
        self.license = "unknown"
        for v in sorted_versions:
            if v.free_pdf_url:
                self.fulltext_url = v.free_pdf_url
                self.evidence = v.source
            elif v.free_pdf_medata_url:
                self.fulltext_url = v.free_pdf_medata_url
                self.evidence = v.source
            if v.license and v.license != "unknown":
                self.license = v.license

        # don't return an open license on a closed thing, that's confusing
        if not self.fulltext_url:
            self.license = "unknown"


    @property
    def is_done(self):
        self.decide_if_open()
        return self.has_fulltext_url and self.license and self.license != "unknown"

    def clear_versions(self):
        self.versions = []
        # also clear summary information
        self.fulltext_url = None
        self.license = None
        self.evidence = None


    def ask_crossref_and_local_lookup(self):
        self.call_crossref()
        self.ask_local_lookup()

    def ask_arxiv(self):
        return

    def ask_pmc(self):
        return

    def ask_hybrid_page(self):
        if self.url:
            self.ask_these_pages([(self.url, "publisher landing page")])
        return

    def ask_base_pages(self):
        oa_base.call_our_base(self)
        # oa_base.call_base([self])

        # print 'self.repo_urls["urls"]', self.repo_urls["urls"]

        base_hits_list = []
        # try any base oa places, to get pdf links when available
        if hasattr(self, "base_dcoa") and self.base_dcoa=="1":
            evidence = "oa repository (via base-search.net oa url)"
            base_hits_list.append([self.fulltext_url, "oa repository (via base-search.net oa url)"])
        # last try is any IRs
        elif hasattr(self, "base_dcoa") and self.base_dcoa=="2":
            for repo_url in self.repo_urls["urls"]:
                evidence = "oa repository (via base-search.net unknown-license url)"
                base_hits_list.append([repo_url, evidence])

        self.ask_these_pages(base_hits_list)
        return




    def find_open_versions(self):
        total_start_time = time()

        targets = [self.ask_crossref_and_local_lookup, self.ask_arxiv, self.ask_pmc]
        call_targets_in_parallel(targets)
        self.decide_if_open()
        if self.is_done:
            return
        print "not done yet!"

        ### set workaround titles
        self.set_workaround_titles()

        targets = [self.ask_hybrid_page, self.ask_base_pages]
        call_targets_in_parallel(targets)

        ### set defaults, like harvard's DASH license
        self.set_open_defaults()

        self.decide_if_open()
        print u"finished all of find_open_versions in {}s".format(elapsed(total_start_time, 2))



    def ask_local_lookup(self):
        start_time = time()

        evidence = None
        fulltext_url = self.url

        license = "unknown"
        if oa_local.is_open_via_doaj_issn(self.issns):
            license = oa_local.is_open_via_doaj_issn(self.issns)
            evidence = "oa journal (via issn in doaj)"
        elif oa_local.is_open_via_doaj_journal(self.journal):
            license = oa_local.is_open_via_doaj_journal(self.journal)
            evidence = "oa journal (via journal title in doaj)"
        elif oa_local.is_open_via_datacite_prefix(self.doi):
            evidence = "oa repository (via datacite prefix)"
        elif oa_local.is_open_via_doi_fragment(self.doi):
            evidence = "oa repository (via doi prefix)"
        elif oa_local.is_open_via_url_fragment(self.url):
            evidence = "oa repository (via url prefix)"
        elif oa_local.is_open_via_license_urls(self.crossref_license_urls):
            freetext_license = oa_local.is_open_via_license_urls(self.crossref_license_urls)
            license = oa_local.find_normalized_license(freetext_license)
            evidence = "hybrid journal (via crossref license url)"  # oa_color depends on this including the word "hybrid"

        if evidence:
            my_version = Version(free_pdf_medata_url=fulltext_url, license=license)
            my_version.source = evidence
            self.versions.append(my_version)


    def ask_these_pages(self, request_list):
        call_args_in_parallel(self.scrape_page_for_open_version, request_list)


    def scrape_page_for_open_version(self, url, evidence):
        print "scraping", url
        scrape_fulltext_url = None
        try:
            (scrape_fulltext_url, scrape_license) = oa_scrape.scrape_for_fulltext_link(url)
            if scrape_fulltext_url or scrape_license and scrape_license!="unknown":
                my_version = Version(free_pdf_url=scrape_fulltext_url, license=scrape_license)
                if evidence == "publisher landing page":
                    my_version.source = u"publisher landing page"   # oa_color depends on this including the word "publisher"
                else:
                    my_version.source = u"scraping of {}".format(evidence)
                self.versions.append(my_version)
                print "found open version at", url
            else:
                print "didn't find open version at", url

        except requests.Timeout, e:
            self.error = "timeout"
            self.error_message = unicode(e.message).encode("utf-8")
        except requests.exceptions.ConnectionError, e:
            self.error = "connection"
            self.error_message = unicode(e.message).encode("utf-8")
        except requests.exceptions.RequestException, e:
            self.error = "other requests error"
            self.error_message = unicode(e.message).encode("utf-8")
        except etree.XMLSyntaxError, e:
            self.error = "xml"
            self.error_message = unicode(e.message).encode("utf-8")
        except Exception, e:
            logging.exception(u"exception in scrape_for_fulltext_link")
            self.error = "other"
            self.error_message = unicode(e.message).encode("utf-8")


    def set_workaround_titles(self):
        workaround_titles = {
            # these preprints doesn't have the same title as the doi
            # eventually solve these by querying arxiv like this:
            # http://export.arxiv.org/api/query?search_query=doi:10.1103/PhysRevD.89.085017
            "10.1016/j.astropartphys.2007.12.004": "In situ radioglaciological measurements near Taylor Dome, Antarctica and implications for UHE neutrino astronomy",
            "10.1016/S0375-9601(02)01803-0": "Universal quantum computation using only projective measurement, quantum memory, and preparation of the 0 state",
            "10.1103/physreva.65.062312": "An entanglement monotone derived from Grover's algorithm",

            # crossref has title "aol" for this
            # set it to real title
            "10.1038/493159a": "Altmetrics: Value all research products",

            # crossref has no title for this
            "10.1038/23891": "Complete quantum teleportation using nuclear magnetic resonance",

            # is a closed-access datacite one, with the open-access version in BASE
            # need to set title here because not looking up datacite titles yet (because ususally open access directly)
            "10.1515/fabl.1988.29.1.21": u"Thesen zur Verabschiedung des Begriffs der 'historischen Sage'",

            # preprint has a different title
            "10.1123/iscj.2016-0037": u"METACOGNITION AND PROFESSIONAL JUDGMENT AND DECISION MAKING: IMPORTANCE, APPLICATION AND EVALUATION"
        }

        if self.doi in workaround_titles:
            self.title = workaround_titles[self.doi]


    def set_open_defaults(self):
        for v in self.versions:
            if v.free_pdf_url and u"dash.harvard.edu" in v.free_pdf_url:
                if not v.license or v.license=="unknown":
                    v.license = "cc-by-nc"

    def call_crossref(self):
        if not self.doi:
            return

        try:
            self.error = None

            proxy_url = os.getenv("STATIC_IP_PROXY")
            proxies = {"https": proxy_url, "http": proxy_url}

            headers={"Accept": "application/json", "User-Agent": "impactstory.org"}
            url = u"https://api.crossref.org/works/{doi}".format(doi=self.doi)

            # print u"calling {} with headers {}".format(url, headers)
            r = requests.get(url, headers=headers, proxies=proxies, timeout=10)  #timeout in seconds
            print "url", url
            if r.status_code == 404: # not found
                self.crossref_api_raw = {"error": "404"}
            elif r.status_code == 200:
                self.crossref_api_raw = r.json()["message"]
            elif r.status_code == 429:
                print u"crossref rate limited!!! status_code=429"
                print u"headers: {}".format(r.headers)
            else:
                self.error = u"got unexpected crossref status_code code {}".format(r.status_code)

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "timeout from requests when getting crossref data"
            print self.error
        except Exception:
            logging.exception("exception in set_crossref_api_raw")
            self.error = "misc error in set_crossref_api_raw"
            print u"in generic exception handler, so rolling back in case it is needed"
            # db.session.rollback()
        finally:
            if self.error:
                print u"ERROR on {doi}: {error}, calling {url}".format(
                    doi=self.doi,
                    error=self.error,
                    url=url)

    @property
    def publisher(self):
        try:
            return self.crossref_api_raw["publisher"]
        except (KeyError, TypeError):
            return None

    @property
    def crossref_license_urls(self):
        try:
            license_dicts = self.crossref_api_raw["license"]
            license_urls = [license_dict["URL"] for license_dict in license_dicts]
            return license_urls
        except (KeyError, TypeError):
            return []

    @property
    def is_subscription_journal(self):
        if oa_local.is_open_via_doaj_issn(self.issns) \
            or oa_local.is_open_via_doaj_journal(self.journal) \
            or oa_local.is_open_via_datacite_prefix(self.doi) \
            or oa_local.is_open_via_doi_fragment(self.doi) \
            or oa_local.is_open_via_url_fragment(self.url):
                return False
        return True

    @property
    def oa_color(self):
        if not self.fulltext_url:
            return None
        if not self.evidence:
            print u"should have evidence for {} but none".format(self.id)
            return None
        if not self.is_subscription_journal:
            return "gold"
        if "publisher" in self.evidence:
            return "gold"
        if "hybrid" in self.evidence:
            return "gold"
        return "green"


    @property
    def doi_resolver(self):
        if not self.doi:
            return None
        if oa_local.is_open_via_datacite_prefix(self.doi):
            return "datacite"
        return "crossref"

    @property
    def is_free_to_read(self):
        if self.fulltext_url:
            return True
        return False

    @property
    def is_boai_license(self):
        boai_licenses = ["cc-by", "cc0", "pd"]
        if self.license and (self.license in boai_licenses):
            return True
        return False

    @property
    def issns(self):
        try:
            return self.crossref_api_raw["ISSN"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def best_title(self):
        if self.title:
            return self.title
        return self.crossref_title

    @property
    def crossref_title(self):
        try:
            return self.crossref_api_raw["title"][0]
        except (AttributeError, TypeError, KeyError, IndexError):
            return None

    @property
    def journal(self):
        try:
            return self.crossref_api_raw["container-title"][0]
        except (AttributeError, TypeError, KeyError, IndexError):
            return None

    @property
    def genre(self):
        try:
            return self.crossref_api_raw["type"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def display_license(self):
        if self.license and self.license=="unknown":
            return None
        return self.license


    def __repr__(self):
        return u"<Publication ({})>".format(self.doi)


    def to_dict(self):
        response = {
            "_title": self.best_title,
            "free_fulltext_url": self.fulltext_url,
            "license": self.display_license,
            "is_subscription_journal": self.is_subscription_journal,
            "oa_color": self.oa_color,
            "doi_resolver": self.doi_resolver,
            "is_boai_license": self.is_boai_license,
            "is_free_to_read": self.is_free_to_read,
            "evidence": self.evidence
        }

        for k in ["doi", "title", "url", "product_id", "key"]:
            value = getattr(self, k, None)
            if value:
                response[k] = value

        sorted_versions = sorted(self.versions, key=lambda x:version_sort_score(x))
        response["open_versions"] = [v.to_dict() for v in sorted_versions]

        if self.error:
            response["error"] = self.error
            response["error_message"] = self.error_message
        return response




