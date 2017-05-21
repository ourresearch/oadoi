from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred
from sqlalchemy import or_
from sqlalchemy import sql
from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy.orm.attributes import flag_modified

from time import time
from time import sleep
from random import random
import datetime
from contextlib import closing
from lxml import etree
from threading import Thread
import logging
import requests
from requests.auth import HTTPProxyAuth
import json
import shortuuid
import os
import sys
import random
from urllib import quote

from app import db

from util import elapsed
from util import clean_doi
from util import safe_commit
from util import remove_punctuation
from util import NoDoiException
import oa_local
import oa_base
from oa_base import get_urls_from_our_base_doc
import oa_manual
from oa_local import find_normalized_license
from open_location import OpenLocation
from open_location import location_sort_score
from reported_noncompliant_copies import reported_noncompliant_url_fragments
from webpage import OpenPublisherWebpage, PublisherWebpage, WebpageInOpenRepo, WebpageInUnknownRepo

COLLECT_VERSION_INFO = False


def call_targets_in_parallel(targets):
    if not targets:
        return

    # print u"calling", targets
    threads = []
    for target in targets:
        process = Thread(target=target, args=[])
        process.start()
        threads.append(process)
    for process in threads:
        try:
            process.join(timeout=30)
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as e:
            print u"thread Exception {} in call_targets_in_parallel. continuing.".format(e)
    # print u"finished the calls to", targets

def call_args_in_parallel(target, args_list):
    # print u"calling", targets
    threads = []
    for args in args_list:
        process = Thread(target=target, args=args)
        process.start()
        threads.append(process)
    for process in threads:
        try:
            process.join(timeout=30)
        except Exception as e:
            print u"thread Exception {} in call_args_in_parallel. continuing.".format(e)
    # print u"finished the calls to", targets


def lookup_product(**biblio):
    my_pub = None
    if "doi" in biblio and biblio["doi"]:
        doi = clean_doi(biblio["doi"])
        my_pub = Crossref.query.get(doi)
        if my_pub:
            print u"found {} in crossref db table!".format(my_pub.id)
            my_pub.reset_vars()
        else:
            my_pub = Crossref(**biblio)
            print u"didn't find {} in crossref db table".format(my_pub)

    if my_pub.publisher == "CrossRef Test Account":
        raise NoDoiException

    return my_pub


def refresh_pub(my_pub, do_commit=False):
    my_pub.refresh()
    db.session.merge(my_pub)
    if do_commit:
        safe_commit(db)
    return my_pub


def thread_result_wrapper(func, args, res):
    res.append(func(*args))


# get rid of this when we get rid of POST endpoint
# for now, simplify it so it just calls the single endpoint
def get_pubs_from_biblio(biblios, run_with_hybrid=False):
    returned_pubs = []
    for biblio in biblios:
        returned_pubs.append(get_pub_from_biblio(biblio, run_with_hybrid))
    return returned_pubs


def get_pub_from_biblio(biblio, run_with_hybrid=False, skip_all_hybrid=False):
    my_pub = lookup_product(**biblio)
    my_pub.refresh(run_with_hybrid=run_with_hybrid, skip_all_hybrid=skip_all_hybrid)

    return my_pub


class PmcidLookup(db.Model):
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'), primary_key=True)
    pmcid = db.Column(db.Text)
    release_date = db.Column(db.Text)
    author_manuscript = db.Column(db.Boolean)


class BaseTitleView(db.Model):
    id = db.Column(db.Text, db.ForeignKey('base.id'), primary_key=True)
    doi = db.Column(db.Text)
    title = db.Column(db.Text)
    normalized_title = db.Column(db.Text, db.ForeignKey('crossref_title_view.normalized_title'))
    body = db.Column(db.Text)


class CrossrefTitleView(db.Model):
    id = db.Column(db.Text, db.ForeignKey('crossref.id'), primary_key=True)
    title = db.Column(db.Text)
    normalized_title = db.Column(db.Text)

    # matching_base_title_views = db.relationship(
    #     'BaseTitleView',
    #     lazy='subquery',
    #     viewonly=True,
    #     backref=db.backref("crossref_title_view", lazy="subquery"),
    #     primaryjoin = "(BaseTitleView.normalized_title==CrossrefTitleView.normalized_title)"
    # )

    @property
    def matching_base_title_views(self):
        q = "select id, body from base where normalize_title(body->'_source'->>'title') = normalize_title('{}') limit 20".format(
            remove_punctuation(self.normalized_title)
        )
        rows = db.engine.execute(q).fetchall()
        return [BaseTitleView(id=row[0], body=row[1]) for row in rows]


class Base(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'))
    body = db.Column(JSONB)

    @property
    def doc(self):
        if not self.body:
            return
        return self.body.get("_source", None)

    def set_doc(self, doc):
        if not self.body:
            self.body = {}
        self.body["_source"] = doc

    def scrape_for_fulltext(self):
        # if self.doc["oa"] == 1:
        #     return

        self.set_webpages()
        response_webpages = []

        found_open_fulltext = False
        for my_webpage in self.webpages:
            if not found_open_fulltext:
                my_webpage.scrape_for_fulltext_link()
                if my_webpage.has_fulltext_url:
                    print u"** found an open version! {}".format(my_webpage.fulltext_url)
                    found_open_fulltext = True
                    response_webpages.append(my_webpage)

        self.open_webpages = response_webpages
        sys.exc_clear()  # someone on the internet said this would fix All The Memory Problems. has to be in the thread.
        return self

    def set_webpages(self):
        self.open_webpages = []
        self.webpages = []
        for url in get_urls_from_our_base_doc(self.doc):
            my_webpage = WebpageInUnknownRepo(url=url)
            self.webpages.append(my_webpage)


    def set_fulltext_urls(self):

        self.fulltext_url_dicts = []
        self.license = None

        # first set license if there is one originally.  overwrite it later if scraped a better one.
        if "license" in self.doc and self.doc["license"]:
            self.license = find_normalized_license(self.doc["license"])

        for my_webpage in self.open_webpages:
            if my_webpage.has_fulltext_url:
                response = {}
                self.fulltext_url_dicts += [{"free_pdf_url": my_webpage.scraped_pdf_url, "pdf_landing_page": my_webpage.url}]
                if not self.license or self.license == "unknown":
                    self.license = my_webpage.scraped_license
            else:
                print "{} has no fulltext url alas".format(my_webpage)

        if self.license == "unknown":
            self.license = None


    def make_action_record(self):

        doc = self.doc

        update_fields = {
            "random": random.random(),
            "fulltext_last_updated": self.fulltext_last_updated,
            "fulltext_url_dicts": self.fulltext_url_dicts,
            "fulltext_license": self.license,
        }

        doc.update(update_fields)
        action = {"doc": doc}
        action["_id"] = self.doc["id"]
        return action

    def update_doc(self):
        self.set_fulltext_urls()
        action_record = self.make_action_record()
        self.doc = action_record["doc"]


    def reset(self):
        self.fulltext_last_updated = datetime.datetime.utcnow().isoformat()
        self.fulltext_url_dicts = []
        self.license = None
        self.set_webpages()


    def find_fulltext(self):
        scrape_start = time()
        self.reset()
        self.scrape_for_fulltext()
        self.set_fulltext_urls()
        action_record = self.make_action_record()
        self.body = {"_id": self.id, "_source": action_record["doc"]}
        # mark the body as dirty, otherwise sqlalchemy doesn't know, doesn't save it
        flag_modified(self, "body")
        print u"find_fulltext took {} seconds".format(elapsed(scrape_start, 2))


    def __repr__(self):
        return u"<Base ({})>".format(self.id)


class Crossref(db.Model):
    id = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    api = db.Column(JSONB)
    response = db.Column(JSONB)
    response_jsonb = db.Column(JSONB)
    tdm_api = db.Column(db.Text)
    response_with_hybrid = db.Column(JSONB)

    pmcid_links = db.relationship(
        'PmcidLookup',
        lazy='subquery',
        viewonly=True,
        cascade="all, delete-orphan",
        backref=db.backref("crossref", lazy="subquery"),
        foreign_keys="PmcidLookup.doi"
    )

    base_doi_links = db.relationship(
        'Base',
        lazy='subquery',
        viewonly=True,
        cascade="all, delete-orphan",
        backref=db.backref("crossref_by_doi", lazy="subquery"),
        foreign_keys="Base.doi"
    )

    normalized_titles = db.relationship(
        'CrossrefTitleView',
        lazy='subquery',
        viewonly=True,
        cascade="all, delete-orphan",
        backref=db.backref("crossref", lazy="subquery"),
        foreign_keys="CrossrefTitleView.id"
    )



    def reset_vars(self):
        if self.id and self.id.startswith("10."):
            self.id = clean_doi(self.id)
        if self.id and not hasattr(self, "doi"):
            self.doi = self.id

        self.license = None
        self.free_metadata_url = None
        self.free_pdf_url = None
        self.fulltext_url = None
        self.error = ""
        self.open_locations = []
        self.closed_urls = []
        self.closed_base_ids = []


    def __init__(self, **biblio):
        self.reset_vars()
        for (k, v) in biblio.iteritems():
            print k, v
            self.__setattr__(k, v)




    @property
    def base_matching_titles(self):
        if self.normalized_titles:
            first_hit = self.normalized_titles[0]
            for base_hit in first_hit.matching_base_title_views:
                return base_hit.id
        return ""

    @property
    def normalized_title(self):
        if self.normalized_titles:
            first_hit = self.normalized_titles[0]
            return first_hit.normalized_title
        return ""

    @property
    def crossref_api_raw(self):
        if self.api and "_source" in self.api:
            return self.api["_source"]
        return self.api

    @property
    def open_base_collection(self):
        if not self.open_base_ids:
            return None
        base_split = self.open_base_ids[0].split(":")
        return base_split[0]

    @property
    def open_base_ids(self):
        # return sorted ids, without dups
        ids = []
        for version in self.sorted_locations:
            if version.base_id and version.base_id not in ids:
                ids.append(version.base_id)
        return ids

    @property
    def open_urls(self):
        # return sorted urls, without dups
        urls = []
        for version in self.sorted_locations:
            if version.best_fulltext_url not in urls:
                urls.append(version.best_fulltext_url)
        return urls
    
    @property
    def url(self):
        return u"http://doi.org/{}".format(self.doi)


    def refresh(self, quiet=False, skip_all_hybrid=False, run_with_hybrid=False):
        self.clear_versions()
        self.find_open_locations(
            skip_all_hybrid=skip_all_hybrid,
            run_with_hybrid=run_with_hybrid
        )
        self.updated = datetime.datetime.utcnow()
        if self.fulltext_url and not quiet:
            print u"**REFRESH found a fulltext_url for {}!  {}: {} **".format(
                self.doi, self.oa_color, self.fulltext_url)


    def run(self, skip_all_hybrid=False, run_with_hybrid=False):
        self.refresh(
            skip_all_hybrid=skip_all_hybrid,
            run_with_hybrid=run_with_hybrid
        )
        self.updated = datetime.datetime.utcnow()
        # self.response = self.to_dict()
        self.response_jsonb = self.to_dict()
        # print json.dumps(self.response_jsonb, indent=4)

    def run_with_skip_all_hybrid(self, quiet=False):
        self.run(skip_all_hybrid=True)


    def run_with_hybrid(self, quiet=False):
        self.refresh(run_with_hybrid=True)
        self.updated = datetime.datetime.utcnow()
        self.response_with_hybrid = self.to_dict()
        # print json.dumps(self.response_with_hybrid, indent=4)



    @property
    def has_been_run(self):
        if self.evidence:
            return True
        return False

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


    def set_overrides(self):
        if not self.doi:
            return

        for (override_doi, override_dict) in oa_manual.get_overrides_dict().iteritems():
            if self.doi == override_doi:
                # reset everything
                self.license = None
                self.free_metadata_url = None
                self.free_pdf_url = None
                self.evidence = "manual"
                self.oa_color = None

                # set just what the override dict specifies
                for (k, v) in override_dict.iteritems():
                    setattr(self, k, v)

                # once override keys are set, make sure we set the fulltext url
                self.set_fulltext_url()
                print u"manual override for {}".format(self.doi)

    def set_fulltext_url(self):
        # give priority to pdf_url
        self.fulltext_url = None
        if self.free_pdf_url:
            self.fulltext_url = self.free_pdf_url
        elif self.free_metadata_url:
            self.fulltext_url = self.free_metadata_url


    def decide_if_open(self, skip_all_hybrid=False):
        # look through the versions here

        # overwrites, hence the sorting
        self.license = None
        self.free_metadata_url = None
        self.free_pdf_url = None
        self.oa_color = None

        reversed_sorted_locations = self.sorted_locations
        reversed_sorted_locations.reverse()

        # go through all the locations, using valid ones to update the best open url data
        for location in reversed_sorted_locations:
            if skip_all_hybrid and location.is_hybrid and location.has_license:
                pass
            else:
                self.free_pdf_url = location.pdf_url
                self.free_metadata_url = location.metadata_url
                self.evidence = location.evidence
                self.oa_color = location.oa_color
                self.version = location.version
                self.license = location.license

        self.set_fulltext_url()

        # don't return an open license on a closed thing, that's confusing
        if not self.fulltext_url:
            self.license = None
            self.evidence = "closed"
            self.oa_color = None
            self.version = None


    @property
    def oa_color_long(self):
        if self.oa_color == "green":
            return "green_only"
        if self.oa_color == "gold":
            return "gold_doaj"
        if self.oa_color == "blue":
            if self.evidence and "via free pdf" in self.evidence:
                return "gold_free"
            else:
                return "gold_hybrid"
        return "closed"

    @property
    def is_done(self):
        self.decide_if_open()
        return self.has_fulltext_url and self.license and self.license != "unknown"

    def clear_versions(self):
        self.reset_vars()

    def ask_arxiv(self):
        return

    def ask_publisher_page(self):
        if self.url:
            publisher_landing_page = PublisherWebpage(url=self.url, related_pub=self)
            self.ask_these_pages([publisher_landing_page])
        return

    def ask_base_pages(self, rescrape_base=False):
        oa_base.call_our_base(self, rescrape_base=rescrape_base)

    def update_open_locations_with_version_info(self):
        open_locations = self.open_locations
        self.open_locations = []
        for my_location in open_locations:
            my_location.version = my_location.find_version()
            self.open_locations.append(my_location)

    @property
    def has_hybrid(self):
        return any([location.is_hybrid for location in self.open_locations])

    @property
    def has_gold(self):
        return any([location.oa_color=="gold" for location in self.open_locations])

    @property
    def green_base_collections(self):
        # return sorted my_collections, without dups
        my_collections = []
        for location in self.green_locations:
            if location.base_collection and location.base_collection not in my_collections:
                my_collections.append(location.base_collection)
        return my_collections

    def find_open_locations(self, skip_all_hybrid=False, run_with_hybrid=False):

        # just based on doi
        self.ask_local_lookup()
        self.ask_pmc()

        # based on titles
        self.set_title_hacks()  # has to be before ask_base_pages, because changes titles
        # self.ask_base_pages(rescrape_base=run_with_hybrid)
        self.ask_base_pages(rescrape_base=False)

        if run_with_hybrid:

            print "\n*****", self.publisher, self.journal
            # look for hybrid
            if  self.has_gold or self.has_hybrid:
                print "we don't have to look for hybrid"
                pass
            else:
                self.ask_publisher_page()

            if COLLECT_VERSION_INFO:
                # do the scraping we need to find version information
                self.update_open_locations_with_version_info()

        # now consolidate
        self.decide_if_open(skip_all_hybrid=skip_all_hybrid)
        self.set_license_hacks()  # has to be after ask_base_pages, because uses repo names
        self.set_overrides()


    def ask_local_lookup(self):
        start_time = time()

        evidence = None
        fulltext_url = self.url

        license = None

        if oa_local.is_open_via_doaj_issn(self.issns, self.year):
            license = oa_local.is_open_via_doaj_issn(self.issns, self.year)
            evidence = "oa journal (via issn in doaj)"
        elif oa_local.is_open_via_doaj_journal(self.all_journals, self.year):
            license = oa_local.is_open_via_doaj_journal(self.all_journals, self.year)
            evidence = "oa journal (via journal title in doaj)"
        elif oa_local.is_open_via_publisher(self.publisher):
            evidence = "oa journal (via publisher name)"
        elif oa_local.is_open_via_datacite_prefix(self.doi):
            evidence = "oa repository (via datacite prefix)"
        elif oa_local.is_open_via_doi_fragment(self.doi):
            evidence = "oa repository (via doi prefix)"
        elif oa_local.is_open_via_url_fragment(self.url):
            evidence = "oa repository (via url prefix)"
        elif oa_local.is_open_via_license_urls(self.crossref_license_urls):
            freetext_license = oa_local.is_open_via_license_urls(self.crossref_license_urls)
            license = oa_local.find_normalized_license(freetext_license)
            print "freetext_license", freetext_license, license
            evidence = "hybrid (via crossref license)"  # oa_color depends on this including the word "hybrid"

        if evidence:
            my_location = OpenLocation()
            my_location.metadata_url = fulltext_url
            my_location.license = license
            my_location.evidence = evidence
            my_location.doi = self.doi
            self.open_locations.append(my_location)


    def ask_pmc(self):
        total_start_time = time()

        for pmc_obj in self.pmcid_links:
            if pmc_obj.release_date == "live":
                my_location = OpenLocation()
                my_location.metadata_url = "http://www.ncbi.nlm.nih.gov/pmc/articles/{}".format(pmc_obj.pmcid.upper())
                my_location.evidence = "oa repository (via pmcid lookup)"
                my_location.doi = self.doi
                self.open_locations.append(my_location)



    # comment out for now so that not scraping by accident
    def ask_these_pages(self, webpages):
        webpage_arg_list = [[page] for page in webpages]
        call_args_in_parallel(self.scrape_page_for_open_version, webpage_arg_list)


    def scrape_page_for_open_version(self, my_webpage):
        # print "scraping", url
        try:
            my_webpage.scrape_for_fulltext_link()
            if my_webpage.is_open:
                my_open_version = my_webpage.mint_open_version()
                self.open_locations.append(my_open_version)
                # print "found open version at", webpage.url
            else:
                # print "didn't find open version at", webpage.url
                pass

        except requests.Timeout, e:
            self.error = "TIMEOUT in scrape_page_for_open_version"
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


    def set_title_hacks(self):
        workaround_titles = {
            # these preprints doesn't have the same title as the doi
            # eventually solve these by querying arxiv like this:
            # http://export.arxiv.org/api/query?search_query=doi:10.1103/PhysRevD.89.085017
            "10.1016/j.astropartphys.2007.12.004": "In situ radioglaciological measurements near Taylor Dome, Antarctica and implications for UHE neutrino astronomy",
            "10.1016/s0375-9601(02)01803-0": "Universal quantum computation using only projective measurement, quantum memory, and preparation of the 0 state",
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


    def set_license_hacks(self):
        if self.fulltext_url and u"harvard.edu/" in self.fulltext_url:
            if not self.license or self.license=="unknown":
                self.license = "cc-by-nc"

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
            license_urls = []

            # only include licenses that are past the start date
            for license_dict in license_dicts:
                valid_now = True
                if license_dict.get("start", None):
                    if license_dict["start"].get("date-time", None):
                        if license_dict["start"]["date-time"] > datetime.datetime.utcnow().isoformat():
                            valid_now = False
                if valid_now:
                    license_urls.append(license_dict["URL"])

            return license_urls
        except (KeyError, TypeError):
            return []

    @property
    def is_subscription_journal(self):
        if oa_local.is_open_via_doaj_issn(self.issns, self.year) \
            or oa_local.is_open_via_doaj_journal(self.all_journals, self.year) \
            or oa_local.is_open_via_datacite_prefix(self.doi) \
            or oa_local.is_open_via_doi_fragment(self.doi) \
            or oa_local.is_open_via_publisher(self.publisher) \
            or oa_local.is_open_via_url_fragment(self.url):
                return False
        return True


    @property
    def doi_resolver(self):
        if not self.doi:
            return None
        if oa_local.is_open_via_datacite_prefix(self.doi):
            return "datacite"
        if self.crossref_api_raw and not "error" in self.crossref_api_raw:
            return "crossref"
        return None

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
    def first_author_lastname(self):
        try:
            return self.crossref_api_raw["first_author_lastname"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def issns(self):
        try:
            return self.crossref_api_raw["ISSN"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def best_title(self):
        if hasattr(self, "title"):
            return self.title
        return self.crossref_title

    @property
    def crossref_title(self):
        try:
            return self.crossref_api_raw["title"]
        except (AttributeError, TypeError, KeyError, IndexError):
            return None

    @property
    def year(self):
        try:
            return self.crossref_api_raw["year"]
        except (AttributeError, TypeError, KeyError, IndexError):
            return None

    @property
    def journal(self):
        try:
            return self.crossref_api_raw["journal"]
        except (AttributeError, TypeError, KeyError, IndexError):
            return None

    @property
    def all_journals(self):
        try:
            return self.crossref_api_raw["all_journals"]
        except (AttributeError, TypeError, KeyError, IndexError):
            return None

    @property
    def genre(self):
        try:
            return self.crossref_api_raw["type"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def sorted_locations(self):
        locations = self.open_locations
        # first sort by best_fulltext_url so ties are handled consistently
        locations = sorted(locations, key=lambda x: x.best_fulltext_url, reverse=False)
        # now sort by what's actually better
        locations = sorted(locations, key=lambda x: location_sort_score(x), reverse=False)

        # now remove noncompliant ones
        locations = [location for location in locations if not location.is_reported_noncompliant]
        return locations

    @property
    def green_locations(self):
        return [location for location in self.sorted_locations if location.oa_color == "green"]

    @property
    def gold_locations(self):
        return [location for location in self.sorted_locations if location.oa_color == "gold"]

    @property
    def blue_locations(self):
        return [location for location in self.sorted_locations if location.oa_color == "blue"]

    def get_resolved_url(self):
        if hasattr(self, "my_resolved_url_cached"):
            return self.my_resolved_url_cached
        try:
            r = requests.get("http://doi.org/{}".format(self.id),
                             stream=True,
                             allow_redirects=True,
                             timeout=(3,3),
                             verify=False
                )

            self.my_resolved_url_cached = r.url

        except Exception:  #hardly ever do this, but man it seems worth it right here
            # print u"get_resolved_url failed"
            self.my_resolved_url_cached = None

        return self.my_resolved_url_cached

    def __repr__(self):
        if self.id:
            my_string = self.id
        else:
            my_string = self.best_title
        return u"<Crossref ({})>".format(my_string)

    @property
    def reported_noncompliant_copies(self):
        return reported_noncompliant_url_fragments(self.doi)

    def learning_row(self):
        return [json.dumps(self.learning_dict()[k]) for k in self.learning_header()]

    def learning_header(self):
        keys = self.learning_dict().keys()
        return sorted(keys)

    def learning_dict(self):
        response = {
            "doi": self.id,
            "journal": self.journal,
            "publisher": self.publisher,
            # "resolved_url": self.get_resolved_url(),  #slow: does a get
            "best_open_url": self.fulltext_url,
            "oa_color": self.oa_color,
            "year": self.year,
            "evidence": self.evidence,
            "open_urls": self.open_urls,
            "open_base_ids": self.open_base_ids,
            "open_base_collection": self.open_base_collection,
            "closed_urls": self.closed_urls,
            "closed_base_ids": self.closed_base_ids
        }
        return response


    def to_dict(self):
        response = {
            # "_title": self.best_title,
            # "_journal": self.journal,
            # "_publisher": self.publisher,
            # "_first_author_lastname": self.first_author_lastname,
            # "_free_pdf_url": self.free_pdf_url,
            # "_free_metadata_url": self.free_metadata_url,
            # "match_type": self.match_type,
            # "_normalized_title": self.normalized_title,
            # "_base_title_views": self.base_matching_titles,
            "free_fulltext_url": self.fulltext_url,
            "_best_open_url": self.fulltext_url,
            "license": self.license,
            "is_subscription_journal": self.is_subscription_journal,
            "oa_color": self.oa_color,
            "oa_color_long": self.oa_color_long,
            "doi_resolver": self.doi_resolver,
            "is_boai_license": self.is_boai_license,
            "is_free_to_read": self.is_free_to_read,
            "year": self.year,
            "evidence": self.evidence,
            "reported_noncompliant_copies": self.reported_noncompliant_copies,
            "found_hybrid": self.blue_locations != [],
            "found_green": self.green_locations != [],
            # "version": self.version,
            "_green_base_collections": self.green_base_collections,
            "_open_base_ids": self.open_base_ids,
            "_open_urls": self.open_urls,
            "_closed_base_ids": self.closed_base_ids
            # "_closed_urls": self.closed_urls,
        }

        for k in ["doi", "title", "url"]:
            value = getattr(self, k, None)
            if value:
                response[k] = value

        # response["copies_green"] = [location.to_dict() for location in self.green_locations]
        # response["copies_gold"] = [location.to_dict() for location in self.gold_locations]
        # response["copies_blue"] = [location.to_dict() for location in self.blue_locations]
        # response["copies_open"] = [location.to_dict() for location in self.sorted_locations]

        if self.error:
            response["error"] = self.error
            response["error_message"] = self.error_message
        return response



# db.create_all()
# commit_success = safe_commit(db)
# if not commit_success:
#     print u"COMMIT fail making objects"
