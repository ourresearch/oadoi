from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred
from sqlalchemy import or_
from sqlalchemy import sql

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
from urllib import quote

from app import db

from util import elapsed
from util import clean_doi
from util import safe_commit
from util import remove_punctuation
import oa_local
import oa_base
from open_version import OpenVersion
from open_version import version_sort_score
from webpage import OpenPublisherWebpage, PublisherWebpage, WebpageInOpenRepo, WebpageInUnknownRepo


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
            print u"found {} in db!".format(my_pub.id)
            my_pub.reset_vars()
        else:
            my_pub = Crossref(**biblio)
            print u"didn't find {} in db".format(my_pub)

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
def get_pubs_from_biblio(biblios, force_refresh=False):
    returned_pubs = []
    for biblio in biblios:
        returned_pubs.append(get_pub_from_biblio(biblio, force_refresh))
    return returned_pubs


def get_pub_from_biblio(biblio, force_refresh=False, save_in_cache=True):
    my_pub = lookup_product(**biblio)
    my_pub.refresh()

    return my_pub


class PmcidLookup(db.Model):
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'), primary_key=True, )
    pmcid = db.Column(db.Text)
    release_date = db.Column(db.Text)

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
    body = db.Column(db.Text)
    doi = db.Column(db.Text, db.ForeignKey('crossref.id'))

class Crossref(db.Model):
    id = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    api = db.Column(JSONB)
    response = db.Column(JSONB)

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

        self.license = "unknown"
        self.free_metadata_url = None
        self.free_pdf_url = None
        self.fulltext_url = None
        self.error = ""
        self.open_versions = []


    def __init__(self, **biblio):
        self.reset_vars()
        for (k, v) in biblio.iteritems():
            print k, v
            self.__setattr__(k, v)

    # just needs a diff name to work around how we call update.py
    def run_subset(self):
        return self.run()

    def run(self):
        self.refresh()
        self.updated = datetime.datetime.utcnow()
        self.response = self.to_dict()

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
    def url(self):
        return u"http://doi.org/{}".format(self.doi)


    def refresh(self):
        if hasattr(self, "fulltext_url"):
            old_fulltext_url = self.fulltext_url
        else:
            old_fulltext_url = None

        self.clear_versions()
        self.find_open_versions()
        self.updated = datetime.datetime.utcnow()
        if old_fulltext_url != self.fulltext_url:
            print u"**REFRESH found a new url for {}! old fulltext_url: {}, new fulltext_url: {} **".format(
                self.doi, old_fulltext_url, self.fulltext_url)

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


    def decide_if_open(self):
        # look through the versions here

        # overwrites, hence the sorting
        self.license = "unknown"
        self.free_metadata_url = None
        self.free_pdf_url = None
        self.fulltext_url = None

        reversed_sorted_versions = self.sorted_versions
        reversed_sorted_versions.reverse()
        for v in reversed_sorted_versions:
            # print "ON VERSION", v, v.pdf_url, v.metadata_url, v.license, v.source
            if v.pdf_url:
                self.free_metadata_url = v.metadata_url
                self.free_pdf_url = v.pdf_url
                self.evidence = v.source
            elif v.metadata_url:
                self.free_metadata_url = v.metadata_url
                self.evidence = v.source
            if v.license and v.license != "unknown":
                self.license = v.license

        if self.free_pdf_url:
            self.fulltext_url = self.free_pdf_url
        elif self.free_metadata_url:
            self.fulltext_url = self.free_metadata_url

        # don't return an open license on a closed thing, that's confusing
        if not self.fulltext_url:
            self.license = "unknown"
            self.evidence = "closed"


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
            if self.open_versions:
                publisher_landing_page = OpenPublisherWebpage(url=self.url, related_pub=self)
            else:
                publisher_landing_page = PublisherWebpage(url=self.url, related_pub=self)
            self.ask_these_pages([publisher_landing_page])
        return

    def ask_base_pages(self):
        if os.getenv("DEPLOYMENT", "staging") == "staging":
            oa_base.call_our_base(self)
        else:
            oa_base.call_our_base_elastic(self)


    def find_open_versions(self):
        total_start_time = time()

        self.ask_local_lookup()
        if not self.open_versions:
            self.ask_pmc()

        ### set workaround titles
        self.set_title_hacks()

        if not self.open_versions:
            self.ask_base_pages()

        ### set defaults, like harvard's DASH license
        self.set_license_hacks()

        self.decide_if_open()



    def ask_local_lookup(self):
        start_time = time()

        evidence = None
        fulltext_url = self.url

        license = "unknown"

        if oa_local.is_open_via_doaj_issn(self.issns):
            license = oa_local.is_open_via_doaj_issn(self.issns)
            evidence = "oa journal (via issn in doaj)"
        elif oa_local.is_open_via_doaj_journal(self.all_journals):
            license = oa_local.is_open_via_doaj_journal(self.all_journals)
            evidence = "oa journal (via journal title in doaj)"
        elif oa_local.is_open_via_datacite_prefix(self.doi):
            evidence = "oa repository (via datacite prefix)"
        elif oa_local.is_open_via_publisher(self.publisher):
            evidence = "oa journal (via publisher name)"
        elif oa_local.is_open_via_doi_fragment(self.doi):
            evidence = "oa repository (via doi prefix)"
        elif oa_local.is_open_via_url_fragment(self.url):
            evidence = "oa repository (via url prefix)"
        elif oa_local.is_open_via_license_urls(self.crossref_license_urls):
            freetext_license = oa_local.is_open_via_license_urls(self.crossref_license_urls)
            license = oa_local.find_normalized_license(freetext_license)
            evidence = "hybrid journal (via crossref license url)"  # oa_color depends on this including the word "hybrid"

        if evidence:
            my_version = OpenVersion()
            my_version.metadata_url = fulltext_url
            my_version.license = license
            my_version.source = evidence
            my_version.doi = self.doi
            self.open_versions.append(my_version)

    def ask_pmc(self):
        total_start_time = time()

        for pmc_obj in self.pmcid_links:
            if pmc_obj.release_date == "live":
                my_version = OpenVersion()
                my_version.metadata_url = "https://www.ncbi.nlm.nih.gov/pmc/articles/{}".format(pmc_obj.pmcid)
                my_version.source = "oa repository (via pmcid lookup)"
                my_version.doi = self.doi
                self.open_versions.append(my_version)



    # comment out for now so that not scraping by accident
    # def ask_these_pages(self, webpages):
    #     webpage_arg_list = [[page] for page in webpages]
    #     call_args_in_parallel(self.scrape_page_for_open_version, webpage_arg_list)


    def scrape_page_for_open_version(self, webpage):
        # print "scraping", url
        try:
            webpage.scrape_for_fulltext_link()
            if webpage.is_open:
                my_open_version = webpage.mint_open_version()
                self.open_versions.append(my_open_version)
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
        for v in self.open_versions:
            if v.metadata_url and u"harvard.edu/" in v.metadata_url:
                if not v.license or v.license=="unknown":
                    v.license = "cc-by-nc"

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
            or oa_local.is_open_via_doaj_journal(self.all_journals) \
            or oa_local.is_open_via_datacite_prefix(self.doi) \
            or oa_local.is_open_via_doi_fragment(self.doi) \
            or oa_local.is_open_via_publisher(self.publisher) \
            or oa_local.is_open_via_url_fragment(self.url):
                return False
        return True

    @property
    def oa_color(self):
        # if self.evidence == "closed":
        #     return "black"
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
    def display_license(self):
        if self.license and self.license=="unknown":
            return None
        return self.license

    @property
    def sorted_versions(self):
        versions = self.open_versions
        # first sort by best_fulltext_url so ties are handled consistently
        versions = sorted(versions, key=lambda x: x.best_fulltext_url, reverse=False)
        # now sort by what's actually better
        versions = sorted(versions, key=lambda x: version_sort_score(x), reverse=False)
        return versions


    def __repr__(self):
        if hasattr(self, "doi"):
            my_string = self.doi
        else:
            my_string = self.best_title
        return u"<Crossref ({})>".format(my_string)


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
            "license": self.display_license,
            "is_subscription_journal": self.is_subscription_journal,
            "oa_color": self.oa_color,
            "doi_resolver": self.doi_resolver,
            "is_boai_license": self.is_boai_license,
            "is_free_to_read": self.is_free_to_read,
            "year": self.year,
            "evidence": self.evidence
        }

        for k in ["doi", "title", "url"]:
            value = getattr(self, k, None)
            if value:
                response[k] = value

        # response["open_versions"] = [v.to_dict() for v in self.sorted_versions]

        if self.error:
            response["error"] = self.error
            response["error_message"] = self.error_message
        return response



# db.create_all()
# commit_success = safe_commit(db)
# if not commit_success:
#     print u"COMMIT fail making objects"

