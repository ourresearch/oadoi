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


def call_local_lookup_oa(product_list):
    start_time = time()
    for my_product in product_list:
        my_product.set_local_lookup_oa()
    print u"finished local step of set_fulltext_urls in {}s".format(elapsed(start_time, 2))


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

def build_product(**request_kwargs):
    my_product = product_from_cache(**request_kwargs)
    if my_product:
        for (k, v) in request_kwargs.iteritems():
            if v:
                value = v.strip()
                setattr(my_product, k, value)
    else:
        my_product = Product(**request_kwargs)
        db.session.add(my_product)
    return my_product


def cache_results(my_products):
    commit_success = safe_commit(db)
    if not commit_success:
        print u"COMMIT fail on caching products"



class Collection(object):
    def __init__(self):
        self.products = []


    def set_fulltext_urls(self):
        total_start_time = time()
        start_time = time()

        print u"starting set_fulltext_urls with {} total products".format(len([p for p in self.products]))
        products_to_check = [p for p in self.products if not p.open_step]
        print u"going to check {} total products".format(len([p for p in products_to_check]))

        print u"STARTING WITH: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))

        print u"SO FAR: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))

        products_for_crossref = [p for p in products_to_check if p.doi and not p.crossref_api_raw]
        call_crossref_in_parallel(products_for_crossref)
        print u"SO FAR: {} open\n".format(len([p for p in self.products if p.has_fulltext_url]))

        ### go see if it is open based on its id
        products_for_lookup = [p for p in products_to_check if not p.has_fulltext_url]
        call_local_lookup_oa(products_for_lookup)
        print u"SO FAR: {} open\n".format(len([p for p in self.products if p.has_fulltext_url]))

        ## check base with everything that isn't yet open and has a title
        products_for_base = [p for p in products_to_check if p.best_title and not p.has_fulltext_url]
        oa_base.call_base(products_for_base)
        print u"SO FAR: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))

        ### check sherlock with all base 2s, all not-yet-open dois and urls, and everything still missing a license
        products_for_scraping = [p for p in products_to_check if not p.has_fulltext_url or not p.has_license]
        call_scrape_in_parallel(products_for_scraping)
        print u"SO FAR: {} open\n".format(len([p for p in products_to_check if p.has_fulltext_url]))

        ## and that's a wrap!
        for p in products_to_check:
            if not p.has_fulltext_url:
                p.open_step = "closed"  # so can tell it didn't error out

        start_time = time()
        cache_results(products_to_check)
        print u"finished caching of set_fulltext_urls in {}s".format(elapsed(start_time, 2))

        print u"finished all of set_fulltext_urls in {}s".format(elapsed(total_start_time, 2))


    def to_dict(self):
        response = [p.to_dict() for p in self.products]
        return response



class Product(db.Model):
    id = db.Column(db.Text, primary_key=True)
    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    doi = db.Column(db.Text)
    url = db.Column(db.Text)
    title = db.Column(db.Text)

    fulltext_url = db.Column(db.Text)
    license = db.Column(db.Text)
    open_step = db.Column(db.Text)

    crossref_api_raw = deferred(db.Column(JSONB))
    error = db.Column(db.Text)
    error_message = db.Column(db.Text)



    def __init__(self, **kwargs):
        self.request_kwargs = kwargs
        self.sherlock_response = None
        self.sherlock_error = None
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
            # print self.doi
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

        open_reason = None
        fulltext_url = self.url

        license = "unknown"
        if oa_local.is_open_via_doaj_issn(self.issns):
            license = oa_local.is_open_via_doaj_issn(self.issns)
            open_reason = "doaj issn"
        elif oa_local.is_open_via_doaj_journal(self.journal):
            license = oa_local.is_open_via_doaj_journal(self.journal)
            open_reason = "doaj journal"
        elif oa_local.is_open_via_datacite_prefix(self.doi):
            open_reason = "datacite prefix"
        elif oa_local.is_open_via_license_url(self.crossref_license_url):
            license = oa_local.find_normalized_license(self.crossref_license_url)
            open_reason = "license url"
        elif oa_local.is_open_via_doi_fragment(self.doi):
            open_reason = "doi fragment"
        elif oa_local.is_open_via_url_fragment(self.url):
            open_reason = "url fragment"

        if open_reason:
            self.fulltext_url = fulltext_url
            self.open_step = u"local lookup: {}".format(open_reason)
            self.license = license



    def scrape_for_oa(self):
        sherlock_request_list = []
        if hasattr(self, "base_dcoa") and self.base_dcoa=="2":
            for repo_url in self.repo_urls["urls"]:
                sherlock_request_list.append(repo_url)
        elif self.url:
            sherlock_request_list.append(self.url)
        else:
            print "not looking up", self.url
            return  # shouldn't have been called

        self.sherlock_response = u"sherlock error: timeout"

        for url in sherlock_request_list:

            try:
                (fulltext_url, license) = oa_scrape.scrape_for_fulltext_link(url)
                # do it this way because don't want to overwrite with None
                if fulltext_url:
                    self.fulltext_url = fulltext_url
                    self.open_step = "scraping"
                self.license = license if license else self.license
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
    def crossref_license_url(self):
        try:
            return self.crossref_api_raw["license"][0]["URL"]
        except (KeyError, TypeError):
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

        for k in ["open_step", "doi", "title", "url", "open_step", "product_id", "key"]:
            value = getattr(self, k, None)
            if value:
                response[k] = value

        if self.error:
            response["error"] = self.error
            response["error_message"] = self.error_message
        return response




