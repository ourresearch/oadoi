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


def lookup_product_in_cache(**biblio):
    my_pub = None
    if "doi" in biblio and biblio["doi"]:
        doi = clean_doi(biblio["doi"])
        my_pub = Cached.query.get(doi)

    if my_pub:
        print u"found {} in db!".format(my_pub)

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


def get_pub_from_biblio(biblio, force_refresh=False):


    ### don't lookup things in cache right now
    # my_pub = None
    # if not force_refresh:
    #     my_pub = lookup_product_in_cache(**biblio)
    #     if my_pub and my_pub.has_been_run:
    #         return my_pub

    my_pub = build_publication(**biblio)
    my_pub.refresh()
    save_publication_in_cache(my_pub)

    return my_pub



def build_publication(**request_kwargs):
    my_pub = Publication(**request_kwargs)
    return my_pub



def save_publication_in_cache(publication_obj):
    my_cached = Cached(publication_obj)
    my_cached.updated = datetime.datetime.utcnow()
    db.session.merge(my_cached)
    safe_commit(db)


class Cached(db.Model):
    id = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    content = db.Column(JSONB)

    def __init__(self, publication_obj):
        self.updated = datetime.datetime.utcnow()
        self.id = publication_obj.doi
        self.content = publication_obj.to_dict()

    @property
    def doi(self):
        return self.id

    @property
    def url(self):
        return u"http://doi.org/{}".format(self.doi)

    @property
    def has_been_run(self):
        return self.content != None

    @property
    def best_redirect_url(self):
        if not self.content:
            return self.url

        if "free_fulltext_url" in self.content:
            return self.content["free_fulltext_url"]
        else:
            return self.url

    def refresh(self):
        my_pub = build_publication(**{"doi": self.doi})
        my_pub.refresh()
        self.content = my_pub.to_dict()
        self.updated = datetime.datetime.utcnow()
        return self.content

    def to_dict(self):
        return self.content


class Publication(db.Model):
    id = db.Column(db.Text, primary_key=True)

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    doi = db.Column(db.Text)
    url = db.Column(db.Text)
    title = db.Column(db.Text)

    fulltext_url = db.Column(db.Text)
    free_pdf_url = db.Column(db.Text)
    free_metadata_url = db.Column(db.Text)
    license = db.Column(db.Text)
    evidence = db.Column(db.Text)

    crossref_api_raw = deferred(db.Column(JSONB))
    error = db.Column(db.Text)
    error_message = db.Column(db.Text)

    open_versions = db.relationship(
        'OpenVersion',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("publication", lazy="subquery"),
        foreign_keys="OpenVersion.pub_id"
    )

    def __init__(self, **kwargs):
        self.request_kwargs = kwargs
        self.base_dcoa = None
        self.repo_urls = {"urls": []}
        self.license_string = ""

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


    def refresh(self):
        old_fulltext_url = self.fulltext_url
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
        self.open_versions = []
        # also clear summary information
        self.fulltext_url = None
        self.license = None
        self.evidence = None


    def ask_crossref_and_local_lookup(self):
        self.call_crossref()
        self.ask_local_lookup()

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
        oa_base.call_our_base(self)
        return


    def find_open_versions(self):
        total_start_time = time()

        targets = [self.ask_crossref_and_local_lookup, self.ask_arxiv, self.ask_pmc]
        call_targets_in_parallel(targets)

        ### set workaround titles
        self.set_title_hacks()

        targets = []
        # don't call publisher pages for now
        # targets = [self.ask_publisher_page]

        if not self.open_versions:
            targets += [self.ask_base_pages]
        call_targets_in_parallel(targets)

        ### set defaults, like harvard's DASH license
        self.set_license_hacks()

        self.decide_if_open()
        print u"finished all of find_open_versions in {} seconds".format(elapsed(total_start_time, 2))


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
            my_version = OpenVersion()
            my_version.metadata_url = fulltext_url
            my_version.license = license
            my_version.source = evidence
            my_version.doi = self.doi
            self.open_versions.append(my_version)

    def ask_pmc(self):
        pmcid = None
        pmcid_query = u"""select pmcid from pmcid_lookup where release_date='live' and doi='{}'""".format(self.doi.lower())
        rows = db.engine.execute(sql.text(pmcid_query)).fetchall()
        if rows:
            pmcid = rows[0][0]

        if pmcid:
            my_version = OpenVersion()
            my_version.metadata_url = "https://www.ncbi.nlm.nih.gov/pmc/articles/{}".format(pmcid)
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


    def set_license_hacks(self):
        for v in self.open_versions:
            if v.metadata_url and u"harvard.edu/" in v.metadata_url:
                if not v.license or v.license=="unknown":
                    v.license = "cc-by-nc"


    def call_crossref(self):
        if not self.doi:
            return

        try:
            self.error = None

            crossref_es_base = os.getenv("CROSSREF_ES_URL")
            quoted_doi = quote(self.doi, safe="")
            record_type = "crosserf_api"  # NOTE THIS HAS A TYPO!  keeping like this here to match the data in ES

            url = u"{crossref_es_base}/crossref/{record_type}/{quoted_doi}".format(
                crossref_es_base=crossref_es_base, record_type=record_type, quoted_doi=quoted_doi)

            # print u"calling {} with headers {}".format(url, headers)
            start_time = time()
            r = requests.get(url, timeout=10)  #timeout in seconds
            print "took {} seconds to call our crossref".format(elapsed(start_time, 2))

            if r.status_code == 404: # not found
                self.crossref_api_raw = {"error": "404"}
            elif r.status_code == 200:
                self.crossref_api_raw = r.json()["_source"]
            elif r.status_code == 429:
                print u"crossref es rate limited!!! status_code=429"
                print u"headers: {}".format(r.headers)
            else:
                self.error = u"got unexpected crossref status_code code {}".format(r.status_code)

        except (KeyboardInterrupt, SystemExit):
            # let these ones through, don't save anything to db
            raise
        except requests.Timeout:
            self.error = "TIMEOUT from requests when getting crossref data"
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
        if self.title:
            return self.title
        return self.crossref_title

    @property
    def crossref_title(self):
        try:
            return self.crossref_api_raw["title"]
        except (AttributeError, TypeError, KeyError, IndexError):
            return None

    @property
    def journal(self):
        try:
            return self.crossref_api_raw["journal"]
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
        my_string = self.doi
        if not my_string:
            my_string = self.best_title
        return u"<Publication ({})>".format(my_string)


    def to_dict(self):
        response = {
            "_title": self.best_title,
            # "_journal": self.journal,
            # "_publisher": self.publisher,
            # "_first_author_lastname": self.first_author_lastname,
            # "_free_pdf_url": self.free_pdf_url,
            # "_free_metadata_url": self.free_metadata_url,
            "free_fulltext_url": self.fulltext_url,
            "license": self.display_license,
            "is_subscription_journal": self.is_subscription_journal,
            "oa_color": self.oa_color,
            "doi_resolver": self.doi_resolver,
            "is_boai_license": self.is_boai_license,
            "is_free_to_read": self.is_free_to_read,
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

