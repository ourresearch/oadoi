from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred
from sqlalchemy import or_

from time import time
import datetime
from contextlib import closing
from lxml import etree
from threading import Thread
import logging
import requests
import shortuuid

from app import db

from util import elapsed
from util import clean_doi
from util import safe_commit
import oa_local
import oa_scrape
import oa_base


def run_collection_from_biblio(use_cache, **biblio):
    my_product = build_product(use_cache, **biblio)
    my_collection = Collection()
    my_collection.products = [my_product]
    my_collection.set_fulltext_urls(use_cache)
    return my_collection


def call_local_lookup_oa(product_list):
    start_time = time()
    for my_product in product_list:
        my_product.set_local_lookup_oa()
    # print u"finished local step of set_fulltext_urls in {}s".format(elapsed(start_time, 2))


def call_scrape_in_parallel(products):
    threads = []
    for my_product in products:
        process = Thread(target=my_product.scrape_for_oa, args=[])
        process.start()
        threads.append(process)

    # wait till all work is done
    for process in threads:
        process.join(timeout=10)

    return products


def call_crossref_in_parallel(products):
    threads = []
    for my_product in products:
        process = Thread(target=my_product.call_crossref, args=[])
        process.start()
        threads.append(process)

    # wait till all work is done
    for process in threads:
        process.join(timeout=5)

    return products


def product_from_cache(**request_kwargs):
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

def build_product(use_cache, **request_kwargs):
    if use_cache:
        my_product = product_from_cache(**request_kwargs)
        if my_product:
            # sets the product_id and any other identifiers the requester gave us
            my_product.response_done = True
            for (k, v) in request_kwargs.iteritems():
                if v:
                    value = v.strip()
                    setattr(my_product, k, value)
    else:
        print u"Skipping cache"
        my_product = None

    if not my_product:
        my_product = Product(**request_kwargs)
        if use_cache:
            db.session.add(my_product)

    return my_product


def cache_results(my_products):
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on caching products"

def set_defaults(my_products):
    for my_product in my_products:
        if my_product.fulltext_url and u"dash.harvard.edu" in my_product.fulltext_url:
            if not my_product.license or my_product.license=="unknown":
                my_product.license = "cc-by-nc"

class Collection(object):
    def __init__(self):
        self.products = []


    def set_fulltext_urls(self, use_cache=True):
        total_start_time = time()
        start_time = time()

        # print u"starting set_fulltext_urls with {} total products".format(len([p for p in self.products]))
        products_to_check = [p for p in self.products if not p.evidence]
        # print u"going to check {} total products".format(len([p for p in products_to_check]))

        # print u"STARTING WITH: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))
        # print u"SO FAR: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))

        products_for_crossref = [p for p in products_to_check if p.doi and not p.response_done]
        call_crossref_in_parallel(products_for_crossref)
        # print u"SO FAR: {} open\n".format(len([p for p in self.products if p.has_fulltext_url]))

        ### go see if it is open based on its id
        products_for_lookup = [p for p in products_to_check if not p.response_done]
        call_local_lookup_oa(products_for_lookup)
        # print u"SO FAR: {} open\n".format(len([p for p in self.products if p.has_fulltext_url]))

        ## check base with everything that isn't yet open and has a title
        products_for_base = [p for p in products_to_check if p.best_title and not p.response_done]
        oa_base.call_base(products_for_base)
        # print u"SO FAR: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))

        ### check oadoi with all base urls, all not-yet-open dois and urls, and everything still missing a license
        products_for_scraping = [p for p in products_to_check if not p.response_done]
        # print "products_for_scraping", products_for_scraping
        call_scrape_in_parallel(products_for_scraping)
        # print u"SO FAR: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))

        ### set defaults, like harvard's DASH license
        set_defaults(products_to_check)

        ## and that's a wrap!
        for p in products_to_check:
            if not p.has_fulltext_url:
                p.evidence = "closed"  # so can tell it didn't error out

        if use_cache:
            start_time = time()
            cache_results(products_to_check)
            # print u"finished caching of set_fulltext_urls in {}s".format(elapsed(start_time, 2))

        for p in self.products:
            if p.has_fulltext_url:
                print u"OPEN {} {} ({}) for {}".format(p.evidence, p.fulltext_url, p.license, p.doi)
            else:
                print u"CLOSED {} ({}) for {}".format(p.fulltext_url, p.license, p.doi)

        print u"finished all of set_fulltext_urls in {}s".format(elapsed(total_start_time, 2))


    def to_dict(self):
        response = [p.to_dict() for p in self.products]
        return response



class Product(db.Model):
    __tablename__ = 'product_cache'

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



    def __init__(self, **kwargs):
        self.request_kwargs = kwargs
        self.base_dcoa = None
        self.response_done = False
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


    def set_local_lookup_oa(self):
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
        elif oa_local.is_open_via_license_urls(self.crossref_license_urls):
            freetext_license = oa_local.is_open_via_license_urls(self.crossref_license_urls)
            license = oa_local.find_normalized_license(freetext_license)
            evidence = "hybrid journal (via crossref license url)"
        elif oa_local.is_open_via_doi_fragment(self.doi):
            evidence = "oa repository (via doi prefix)"
        elif oa_local.is_open_via_url_fragment(self.url):
            evidence = "oa repository (via url prefix)"

        if evidence:
            self.fulltext_url = fulltext_url
            self.evidence = evidence
            self.license = license
        if self.fulltext_url and self.license and self.license != "unknown":
            self.response_done = True



    def scrape_for_oa(self):
        request_list = []

        # try the publisher first
        if self.url:
            request_list.append([self.url, "publisher landing page"])

        # then any oa places, to get pdf links when available
        if hasattr(self, "base_dcoa") and self.base_dcoa=="1":
            evidence = "oa repository (via base-search.net oa url)"
            request_list.append([self.fulltext_url, "oa repository (via base-search.net oa url)"])

        # last try is any IRs
        elif hasattr(self, "base_dcoa") and self.base_dcoa=="2":
            for repo_url in self.repo_urls["urls"]:
                evidence = "oa repository (via base-search.net unknown-license url)"
                request_list.append([repo_url, evidence])

        print u"scrape_for_oa request_list: {}".format(request_list)

        for (url, source) in request_list:
            print u"trying {} {}".format(url, source)
            try:
                (scrape_fulltext_url, scrape_license) = oa_scrape.scrape_for_fulltext_link(url)

                # set these this way because we don't want to overwrite with Nones
                if scrape_license:
                    self.license = scrape_license

                # if we found a scraped url!  use it :)
                if scrape_fulltext_url:
                    self.fulltext_url = scrape_fulltext_url
                    if source == "publisher landing page":
                        self.evidence = u"publisher landing page"
                    else:
                        self.evidence = u"scraping of {}".format(source)
                    self.response_done = True
                    return

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

        # have tried everything.  we might have a free_fulltext from a base1 but
        # didn't get a scrape url.  in this case we can still declare success :)
        if self.has_fulltext_url:
            self.response_done = True



    def call_crossref(self):
        if not self.doi:
            return

        try:
            self.error = None

            headers={"Accept": "application/json", "User-Agent": "impactstory.org"}
            url = u"http://api.crossref.org/works/{doi}".format(doi=self.doi)

            # print u"calling {} with headers {}".format(url, headers)
            r = requests.get(url, headers=headers, timeout=10)  #timeout in seconds
            if r.status_code == 404: # not found
                self.crossref_api_raw = {"error": "404"}
            elif r.status_code == 200:
                self.crossref_api_raw = r.json()["message"]
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


    def to_dict(self):
        response = {
            "free_fulltext_url": self.fulltext_url,
            "license": self.license,
        }

        for k in ["evidence", "doi", "title", "url", "evidence", "product_id", "key"]:
            value = getattr(self, k, None)
            if value:
                response[k] = value

        if self.error:
            response["error"] = self.error
            response["error_message"] = self.error_message
        return response




