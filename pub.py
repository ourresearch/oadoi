from time import time
import datetime
from lxml import etree
from threading import Thread
import requests
import shortuuid
import re
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import orm
from collections import Counter

from app import db
from app import logger
from util import clean_doi
from util import safe_commit
from util import NoDoiException
from util import normalize
from util import normalize_title
import oa_local
from pmh_record import title_is_too_common
from pmh_record import title_is_too_short
import oa_manual
from open_location import OpenLocation
from reported_noncompliant_copies import reported_noncompliant_url_fragments
from webpage import PublisherWebpage
from http_cache import get_session_id


def call_targets_in_parallel(targets):
    if not targets:
        return

    # logger.info(u"calling", targets)
    threads = []
    for target in targets:
        process = Thread(target=target, args=[])
        process.start()
        threads.append(process)
    for process in threads:
        try:
            process.join(timeout=60*10)
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as e:
            logger.info(u"thread Exception {} in call_targets_in_parallel. continuing.".format(e))
    # logger.info(u"finished the calls to {}".format(targets))

def call_args_in_parallel(target, args_list):
    # logger.info(u"calling", targets)
    threads = []
    for args in args_list:
        process = Thread(target=target, args=args)
        process.start()
        threads.append(process)
    for process in threads:
        try:
            process.join(timeout=60*10)
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as e:
            logger.info(u"thread Exception {} in call_args_in_parallel. continuing.".format(e))
    # logger.info(u"finished the calls to {}".format(targets))


def lookup_product_by_doi(doi):
    biblio = {"doi": doi}
    return lookup_product(**biblio)


def lookup_product(**biblio):
    my_pub = None
    if "doi" in biblio and biblio["doi"]:
        doi = clean_doi(biblio["doi"])
        my_pub = Pub.query.get(doi)
        if my_pub:
            logger.info(u"found {} in pub db table!".format(my_pub.id))
            my_pub.reset_vars()
        else:
            raise NoDoiException
        #     my_pub = Crossref(**biblio)
        #     logger.info(u"didn't find {} in crossref db table".format(my_pub))

    return my_pub


def refresh_pub(my_pub, do_commit=False):
    my_pub.run_with_hybrid()
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
        returned_pubs.append(get_pub_from_biblio(biblio, run_with_hybrid=run_with_hybrid))
    return returned_pubs


def get_pub_from_biblio(biblio, run_with_hybrid=False, skip_all_hybrid=False):
    my_pub = lookup_product(**biblio)
    if run_with_hybrid:
        my_pub.run_with_hybrid()
        safe_commit(db)
    else:
        my_pub.recalculate()

    return my_pub

def max_pages_from_one_repo(repo_ids):
    repo_id_counter = Counter(repo_ids)
    most_common = repo_id_counter.most_common(1)
    if most_common:
        return most_common[0][1]
    return None

def get_citeproc_date(year=0, month=1, day=1):
    try:
        return datetime.datetime(year, month, day).isoformat()
    except ValueError:
        return None


def build_crossref_record(data):
    record = {}

    simple_fields = [
        "publisher",
        "subject",
        "link",
        "license",
        "funder",
        "type",
        "update-to",
        "clinical-trial-number",
        "ISSN",  # needs to be uppercase
        "ISBN",  # needs to be uppercase
        "alternative-id"
    ]

    for field in simple_fields:
        if field in data:
            record[field.lower()] = data[field]

    if "title" in data:
        if isinstance(data["title"], basestring):
            record["title"] = data["title"]
        else:
            if data["title"]:
                record["title"] = data["title"][0]  # first one
        if "title" in record and record["title"]:
            record["title"] = re.sub(u"\s+", u" ", record["title"])


    if "container-title" in data:
        record["all_journals"] = data["container-title"]
        if isinstance(data["container-title"], basestring):
            record["journal"] = data["container-title"]
        else:
            if data["container-title"]:
                record["journal"] = data["container-title"][-1] # last one
        # get rid of leading and trailing newlines
        if record.get("journal", None):
            record["journal"] = record["journal"].strip()

    if "author" in data:
        # record["authors_json"] = json.dumps(data["author"])
        record["all_authors"] = data["author"]
        if data["author"]:
            first_author = data["author"][0]
            if first_author and u"family" in first_author:
                record["first_author_lastname"] = first_author["family"]
            for author in record["all_authors"]:
                if author and "affiliation" in author and not author.get("affiliation", None):
                    del author["affiliation"]


    if "issued" in data:
        # record["issued_raw"] = data["issued"]
        try:
            if "raw" in data["issued"]:
                record["year"] = int(data["issued"]["raw"])
            elif "date-parts" in data["issued"]:
                record["year"] = int(data["issued"]["date-parts"][0][0])
                date_parts = data["issued"]["date-parts"][0]
                pubdate = get_citeproc_date(*date_parts)
                if pubdate:
                    record["pubdate"] = pubdate
        except (IndexError, TypeError):
            pass

    if "deposited" in data:
        try:
            record["deposited"] = data["deposited"]["date-time"]
        except (IndexError, TypeError):
            pass


    record["added_timestamp"] = datetime.datetime.utcnow().isoformat()
    return record



class CrossrefApi(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text, db.ForeignKey('pub.id'))
    updated = db.Column(db.DateTime)
    api_raw = db.Column(JSONB)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.updated = datetime.datetime.utcnow()
        super(CrossrefApi, self).__init__(**kwargs)


class PmcidLookup(db.Model):
    doi = db.Column(db.Text, db.ForeignKey('pub.id'), primary_key=True)
    pmcid = db.Column(db.Text)
    release_date = db.Column(db.Text)



class Pub(db.Model):
    id = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    api = db.Column(JSONB)
    api_raw = db.Column(JSONB)
    tdm_api = db.Column(db.Text)  #is in XML
    title = db.Column(db.Text)
    normalized_title = db.Column(db.Text)
    issns_jsonb = db.Column(JSONB)

    last_changed_date = db.Column(db.DateTime)
    response_jsonb = db.Column(JSONB)
    response_v1 = db.Column(JSONB)
    response_is_oa = db.Column(db.Boolean)
    response_best_evidence = db.Column(db.Text)
    response_best_url = db.Column(db.Text)

    scrape_updated = db.Column(db.DateTime)
    scrape_evidence = db.Column(db.Text)
    scrape_pdf_url = db.Column(db.Text)
    scrape_metadata_url = db.Column(db.Text)
    scrape_license = db.Column(db.Text)

    error = db.Column(db.Text)

    started = db.Column(db.DateTime)
    finished = db.Column(db.DateTime)
    rand = db.Column(db.Numeric)

    pmcid_links = db.relationship(
        'PmcidLookup',
        lazy='subquery',
        viewonly=True,
        cascade="all, delete-orphan",
        backref=db.backref("pub", lazy="subquery"),
        foreign_keys="PmcidLookup.doi"
    )

    page_matches_by_doi = db.relationship(
        'Page',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("pub_by_doi", lazy="subquery"),
        foreign_keys="Page.doi"
    )

    page_matches_by_title = db.relationship(
        'Page',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("pub_by_title", lazy="subquery"),
        foreign_keys="Page.normalized_title"
    )

    crossref_api_raw_fresh = db.relationship(
        'CrossrefApi',
        lazy='subquery',
        viewonly=True,
        cascade="all, delete-orphan",
        backref=db.backref("pub", lazy="subquery"),
        foreign_keys="CrossrefApi.doi"
    )

    def __init__(self, **biblio):
        self.reset_vars()
        for (k, v) in biblio.iteritems():
            self.__setattr__(k, v)

    @orm.reconstructor
    def init_on_load(self):
        self.reset_vars()


    def reset_vars(self):
        if self.id and self.id.startswith("10."):
            self.id = clean_doi(self.id)

        self.license = None
        self.free_metadata_url = None
        self.free_pdf_url = None
        self.fulltext_url = None
        self.oa_color = None
        self.evidence = None
        self.open_locations = []
        self.closed_urls = []
        self.session_id = None
        self.version = None

    @property
    def doi(self):
        return self.id

    @property
    def crossref_api_raw_fresh_api_raw(self):
        try:
            record = build_crossref_record(self.crossref_api_raw_fresh[0].api_raw)
            return record
        except IndexError:
            pass
        return None


    @property
    def crossref_api_raw(self):
        record = None
        if self.api_raw:
            try:
                return self.api_raw
            except IndexError:
                pass

        try:
            record = build_crossref_record(self.crossref_api_raw_fresh[0].api_raw)
            return record
        except IndexError:
            pass


        return record


    @property
    def open_urls(self):
        # return sorted urls, without dups
        urls = []
        for version in self.sorted_locations:
            if version.best_url not in urls:
                urls.append(version.best_url)
        return urls
    
    @property
    def url(self):
        return u"https://doi.org/{}".format(self.id)

    @property
    def is_oa(self):
        if self.fulltext_url:
            return True
        return False


    def recalculate(self, quiet=False):
        self.clear_locations()

        if self.publisher == "CrossRef Test Account":
            self.error += "CrossRef Test Account"
            raise NoDoiException

        self.find_open_locations()

        if self.fulltext_url and not quiet:
            logger.info(u"**REFRESH found a fulltext_url for {}!  {}: {} **".format(
                self.id, self.oa_status, self.fulltext_url))


    def refresh(self, session_id=None):
        if session_id:
            self.session_id = session_id
        else:
            self.session_id = get_session_id()

        self.refresh_green_locations()

        self.refresh_hybrid_scrape()

        # and then recalcualte everything, so can do to_dict() after this and it all works
        self.recalculate()



    def set_results(self):
        self.updated = datetime.datetime.utcnow()
        self.issns_jsonb = self.issns
        self.response_jsonb = self.to_dict_v2()
        self.response_v1 = self.to_dict()
        self.response_is_oa = self.is_oa
        self.response_best_url = self.best_url
        self.response_best_evidence = self.best_evidence

    def clear_results(self):
        self.response_jsonb = None
        self.response_v1 = None
        self.response_is_oa = None
        self.response_best_url = None
        self.response_best_evidence = None
        self.error = ""
        self.issns_jsonb = None


    def has_changed(self, old_response_jsonb):

        if not old_response_jsonb:
            logger.info(u"response for {} has changed: no old response".format(self.id))
            return True

        old_best_oa_location = old_response_jsonb.get("best_oa_location", {})
        if not old_best_oa_location:
            old_best_oa_location = {}
        new_best_oa_location = self.response_jsonb.get("best_oa_location", {})
        if not new_best_oa_location:
            new_best_oa_location = {}

        if new_best_oa_location and not old_best_oa_location:
            logger.info(u"response for {} has changed: no old oa location".format(self.id))
            return True

        if old_best_oa_location and not new_best_oa_location:
            oa_locations = old_response_jsonb.get("oa_locations", [])
            pmh_ids = [loc["id"] for loc in oa_locations if loc["id"] and u":" in id]
            repo_ids = [id.split(":")[1] for id in pmh_ids]
            logger.info(u"response for {} has changed: now closed.  old url was {}, had {} copies from one repo which is too many".format(
                self.id,
                old_best_oa_location.get("url", None),
                max_pages_from_one_repo(repo_ids)))
            return True

        if new_best_oa_location.get("url", None) != old_best_oa_location.get("url", None):
            logger.info(u"response for {} has changed: url is now {}, was {}".format(
                self.id,
                new_best_oa_location.get("url", None),
                old_best_oa_location.get("url", None)))
            return True
        if new_best_oa_location.get("url_for_landing_page", None) != old_best_oa_location.get("url_for_landing_page", None):
            return True
        if new_best_oa_location.get("url_for_pdf", None) != old_best_oa_location.get("url_for_pdf", None):
            return True
        if new_best_oa_location.get("host_type", None) != old_best_oa_location.get("host_type", None):
            logger.info(u"response for {} has changed: host_type is now {}".format(self.id, new_best_oa_location.get("host_type", None)))
            return True
        if new_best_oa_location.get("version", None) != old_best_oa_location.get("version", None):
            logger.info(u"response for {} has changed: version is now {}".format(self.id, new_best_oa_location.get("version", None)))
            return True
        if self.response_jsonb["journal_is_oa"] != old_response_jsonb["journal_is_oa"] and (self.response_jsonb["journal_is_oa"] or old_response_jsonb["journal_is_oa"]):
            logger.info(u"response for {} has changed: journal_is_oa is now {}".format(self.id, self.response_jsonb["journal_is_oa"]))
            return True

        return False


    def update(self):
        self.crossref_api_raw_new = self.crossref_api_raw_fresh_api_raw
        self.normalized_title = normalize_title(self.title)

        old_response_jsonb = self.response_jsonb

        self.clear_results()
        try:
            self.recalculate()
        except NoDoiException:
            logger.info(u"invalid doi {}".format(self))
            self.error += "Invalid DOI"
            pass

        self.set_results()

        if self.has_changed(old_response_jsonb):
            self.last_changed_date = datetime.datetime.utcnow().isoformat()



    def run(self):
        self.clear_results()
        try:
            self.recalculate()
        except NoDoiException:
            logger.info(u"invalid doi {}".format(self))
            self.error += "Invalid DOI"
            pass
        self.set_results()
        # logger.info(json.dumps(self.response_jsonb, indent=4))


    def run_with_hybrid(self, quiet=False, shortcut_data=None):
        logger.info(u"in run_with_hybrid")
        self.clear_results()
        try:
            self.refresh()
        except NoDoiException:
            logger.info(u"invalid doi {}".format(self))
            self.error += "Invalid DOI"
            pass
        self.set_results()


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
        if not self.id:
            return None
        return clean_doi(self.id)

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
                logger.info(u"manual override for {}".format(self.doi))


    def set_fulltext_url(self):
        # give priority to pdf_url
        self.fulltext_url = None
        if self.free_pdf_url:
            self.fulltext_url = self.free_pdf_url
        elif self.free_metadata_url:
            self.fulltext_url = self.free_metadata_url


    def decide_if_open(self):
        # look through the locations here

        # overwrites, hence the sorting
        self.license = None
        self.free_metadata_url = None
        self.free_pdf_url = None
        self.oa_color = None
        self.version = None
        self.evidence = None

        reversed_sorted_locations = self.sorted_locations
        reversed_sorted_locations.reverse()

        # go through all the locations, using valid ones to update the best open url data
        for location in reversed_sorted_locations:
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
            self.evidence = None
            self.oa_color = None
            self.version = None


    @property
    def oa_status(self):
        if self.oa_color == "green":
            return "green"
        if self.oa_color == "gold":
            return "gold"
        if self.oa_color in ["blue", "bronze"]:
            return "bronze"
        return "closed"

    @property
    def is_done(self):
        self.decide_if_open()
        return self.has_fulltext_url and self.license and self.license != "unknown"

    def clear_locations(self):
        self.reset_vars()



    @property
    def has_hybrid(self):
        return any([location.is_hybrid for location in self.open_locations])

    @property
    def has_gold(self):
        return any([location.oa_color=="gold" for location in self.open_locations])

    def refresh_green_locations(self):
        for my_page in self.pages:
            my_page.scrape()


    def refresh_hybrid_scrape(self):
        logger.info(u"***** {}: {}".format(self.publisher, self.journal))
        # look for hybrid
        self.scrape_updated = datetime.datetime.utcnow().isoformat()

        # reset
        self.scrape_evidence = None
        self.scrape_pdf_url = None
        self.scrape_metadata_url = None
        self.scrape_license = None

        if self.url:
            publisher_landing_page = PublisherWebpage(url=self.url, related_pub=self)
            self.scrape_page_for_open_location(publisher_landing_page)
            if publisher_landing_page.is_open:
                self.scrape_evidence = publisher_landing_page.open_version_source_string
                self.scrape_pdf_url = publisher_landing_page.scraped_pdf_url
                self.scrape_metadata_url = publisher_landing_page.scraped_open_metadata_url
                self.scrape_license = publisher_landing_page.scraped_license
                if publisher_landing_page.is_open and not publisher_landing_page.scraped_pdf_url:
                    self.scrape_metadata_url = self.url
        return


    def find_open_locations(self, skip_all_hybrid=False, run_with_hybrid=False):

        # just based on doi
        self.ask_local_lookup()
        self.ask_pmc()

        # based on titles
        self.set_title_hacks()  # has to be before ask_green_locations, because changes titles

        self.ask_green_locations()
        self.ask_hybrid_scrape()

        # hack for now, till refactor done, to set pmc versions
        for loc in self.open_locations:
            if loc.is_pmc:
                loc.set_pmc_version()

        # now consolidate
        self.decide_if_open()
        self.set_license_hacks()  # has to be after ask_green_locations, because uses repo names
        self.set_overrides()


    def ask_local_lookup(self):
        start_time = time()

        evidence = None
        fulltext_url = self.url

        license = None

        if oa_local.is_open_via_doaj_issn(self.issns, self.year):
            license = oa_local.is_open_via_doaj_issn(self.issns, self.year)
            evidence = "oa journal (via issn in doaj)"
        elif not self.issns and oa_local.is_open_via_doaj_journal(self.all_journals, self.year):
            license = oa_local.is_open_via_doaj_journal(self.all_journals, self.year)
            evidence = "oa journal (via journal title in doaj)"
        elif oa_local.is_open_via_publisher(self.publisher):
            evidence = "oa journal (via publisher name)"
        elif oa_local.is_open_via_doi_fragment(self.doi):
            evidence = "oa repository (via doi prefix)"
        elif oa_local.is_open_via_url_fragment(self.url):
            evidence = "oa repository (via url prefix)"
        elif oa_local.is_open_via_license_urls(self.crossref_license_urls):
            freetext_license = oa_local.is_open_via_license_urls(self.crossref_license_urls)
            license = oa_local.find_normalized_license(freetext_license)
            # logger.info(u"freetext_license: {} {}".format(freetext_license, license))
            evidence = "open (via crossref license)"  # oa_color depends on this including the word "hybrid"

        if evidence:
            my_location = OpenLocation()
            my_location.metadata_url = fulltext_url
            my_location.license = license
            my_location.evidence = evidence
            my_location.updated = datetime.datetime.utcnow()
            my_location.doi = self.doi
            my_location.version = "publishedVersion"
            self.open_locations.append(my_location)


    def ask_pmc(self):
        total_start_time = time()

        for pmc_obj in self.pmcid_links:
            if pmc_obj.release_date == "live":
                my_location = OpenLocation()
                my_location.metadata_url = "https://www.ncbi.nlm.nih.gov/pmc/articles/{}".format(pmc_obj.pmcid.upper())
                my_location.pdf_url = "https://www.ncbi.nlm.nih.gov/pmc/articles/{}/pdf".format(pmc_obj.pmcid.upper())
                my_location.evidence = "oa repository (via pmcid lookup)"
                my_location.updated = datetime.datetime.utcnow()
                my_location.doi = self.doi
                # set version in one central place for pmc right now, till refactor done
                self.open_locations.append(my_location)

    @property
    def has_stored_hybrid_scrape(self):
        return (self.scrape_evidence and self.scrape_evidence != "closed")

    def ask_hybrid_scrape(self):
        if self.has_stored_hybrid_scrape:
            my_location = OpenLocation()
            my_location.pdf_url = self.scrape_pdf_url
            my_location.metadata_url = self.scrape_metadata_url
            my_location.license = self.scrape_license
            my_location.evidence = self.scrape_evidence
            my_location.updated = self.scrape_updated
            my_location.doi = self.doi
            my_location.version = "publishedVersion"
            self.open_locations.append(my_location)


    @property
    def page_matches_by_title_filtered(self):

        my_pages = []

        if not self.normalized_title:
            return my_pages

        for my_page in self.page_matches_by_title:
            # don't do this right now.  not sure if it helps or hurts.
            # don't check title match if we already know it belongs to a different doi
            # if my_page.doi and my_page.doi != self.doi:
            #     continue

            # double check author match
            match_type = "title"
            if self.first_author_lastname or self.last_author_lastname:
                if my_page.authors:
                    try:
                        pmh_author_string = u", ".join(my_page.authors)
                        if self.first_author_lastname and normalize(self.first_author_lastname) in normalize(pmh_author_string):
                            match_type = "title and first author"
                        elif self.last_author_lastname and normalize(self.last_author_lastname) in normalize(pmh_author_string):
                            match_type = "title and last author"
                        else:
                            logger.info(u"author check fails, so skipping this record. Looked for {} and {} in {}".format(
                                self.first_author_lastname, self.last_author_lastname, pmh_author_string))
                            logger.info(self.authors)
                            # don't match if bad author match
                            continue
                    except TypeError:
                        pass # couldn't make author string
            my_page.scrape_evidence = u"oa repository (via OAI-PMH {} match)".format(match_type)
            my_pages.append(my_page)
        return my_pages

    @property
    def pages(self):
        my_pages = []

        if self.normalized_title:
            if title_is_too_short(self.normalized_title):
                # logger.info(u"title too short! don't match by title")
                pass
            elif title_is_too_common(self.normalized_title):
                # logger.info(u"title too common!  don't match by title.")
                pass
            else:
                my_pages = self.page_matches_by_title_filtered

        # do dois last, because the objects are actually the same, not copies, and then they get the doi reason
        for my_page in self.page_matches_by_doi:
            my_page.scrape_evidence = u"oa repository (via OAI-PMH doi match)"
            my_pages.append(my_page)

        # eventually only apply this filter to matches by title, once pages only includes
        # the doi when it comes straight from the pmh record
        if max_pages_from_one_repo([p.repo_id for p in self.page_matches_by_title_filtered]) >= 3:
            my_pages = []
            logger.info(u"matched too many pages in one repo, not allowing matches")

        return my_pages

    def ask_green_locations(self):
        has_new_green_locations = False
        for green_location in self.pages:
            if green_location.is_open:
                new_open_location = OpenLocation()
                new_open_location.pdf_url = green_location.scrape_pdf_url
                new_open_location.metadata_url = green_location.scrape_metadata_url
                new_open_location.license = green_location.scrape_license
                new_open_location.evidence = green_location.scrape_evidence
                new_open_location.version = green_location.scrape_version
                new_open_location.updated = green_location.scrape_updated
                new_open_location.doi = green_location.doi
                new_open_location.pmh_id = green_location.id
                self.open_locations.append(new_open_location)
                has_new_green_locations = True
        return has_new_green_locations


    # comment out for now so that not scraping by accident
    # def scrape_these_pages(self, webpages):
    #     webpage_arg_list = [[page] for page in webpages]
    #     call_args_in_parallel(self.scrape_page_for_open_location, webpage_arg_list)


    def scrape_page_for_open_location(self, my_webpage):
        # logger.info(u"scraping", url)
        try:
            my_webpage.scrape_for_fulltext_link()

            if my_webpage.error:
                self.error += my_webpage.error

            if my_webpage.is_open:
                my_open_location = my_webpage.mint_open_location()
                self.open_locations.append(my_open_location)
                # logger.info(u"found open version at", webpage.url)
            else:
                # logger.info(u"didn't find open version at", webpage.url)
                pass

        except requests.Timeout, e:
            self.error += "Timeout in scrape_page_for_open_location on {}: {}".format(my_webpage, unicode(e.message).encode("utf-8"))
            logger.info(self.error)
        except requests.exceptions.ConnectionError, e:
            self.error += "ConnectionError in scrape_page_for_open_location on {}: {}".format(my_webpage, unicode(e.message).encode("utf-8"))
            logger.info(self.error)
        except requests.exceptions.ChunkedEncodingError, e:
            self.error += "ChunkedEncodingError in scrape_page_for_open_location on {}: {}".format(my_webpage, unicode(e.message).encode("utf-8"))
            logger.info(self.error)
        except requests.exceptions.RequestException, e:
            self.error += "RequestException in scrape_page_for_open_location on {}: {}".format(my_webpage, unicode(e.message).encode("utf-8"))
            logger.info(self.error)
        except etree.XMLSyntaxError, e:
            self.error += "XMLSyntaxError in scrape_page_for_open_location on {}: {}".format(my_webpage, unicode(e.message).encode("utf-8"))
            logger.info(self.error)
        except Exception, e:
            self.error += "Exception in scrape_page_for_open_location on {}: {}".format(my_webpage, unicode(e.message).encode("utf-8"))
            logger.info(self.error)


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
            return self.crossref_api_raw["publisher"].replace("\n", "")
        except (KeyError, TypeError, AttributeError):
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
    def authors(self):
        try:
            return self.crossref_api_raw["all_authors"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def first_author_lastname(self):
        try:
            return self.crossref_api_raw["first_author_lastname"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def last_author_lastname(self):
        try:
            last_author = self.authors[-1]
            return last_author["family"]
        except (AttributeError, TypeError, KeyError):
            return None

    @property
    def display_issns(self):
        if self.issns:
            return ",".join(self.issns)
        return None

    @property
    def issns(self):
        issns = []
        try:
            issns = self.crossref_api_raw["issn"]
        except (AttributeError, TypeError, KeyError):
            try:
                issns = self.crossref_api_raw["issn"]
            except (AttributeError, TypeError, KeyError):
                if self.tdm_api:
                    issns = re.findall(u"<issn media_type=.*>(.*)</issn>", self.tdm_api)
        if not issns:
            return None
        else:
            return issns

    @property
    def best_title(self):
        if hasattr(self, "title") and self.title:
            return self.title.replace("\n", "")
        return self.crossref_title

    @property
    def crossref_title(self):
        try:
            return self.crossref_api_raw["title"].replace("\n", "")
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
    def deduped_sorted_locations(self):
        locations = []
        for next_location in self.sorted_locations:
            urls_so_far = [location.best_url for location in locations]
            if next_location.best_url not in urls_so_far:
                locations.append(next_location)
        return locations

    @property
    def sorted_locations(self):
        locations = self.open_locations
        # first sort by best_url so ties are handled consistently
        locations = sorted(locations, key=lambda x: x.best_url, reverse=False)
        # now sort by what's actually better
        locations = sorted(locations, key=lambda x: x.sort_score, reverse=False)

        # now remove noncompliant ones
        locations = [location for location in locations if not location.is_reported_noncompliant]
        return locations

    @property
    def data_standard(self):
        # if self.scrape_updated or self.oa_status in ["gold", "hybrid", "bronze"]:
        if self.scrape_updated and not self.error:
            return 2
        else:
            return 1

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
            # logger.info(u"get_resolved_url failed")
            self.my_resolved_url_cached = None

        return self.my_resolved_url_cached

    def __repr__(self):
        if self.id:
            my_string = self.id
        else:
            my_string = self.best_title
        return u"<Pub ({})>".format(my_string)

    @property
    def reported_noncompliant_copies(self):
        return reported_noncompliant_url_fragments(self.doi)

    def is_same_publisher(self, publisher):
        if self.publisher:
            return normalize(self.publisher) == normalize(publisher)
        return False

    @property
    def best_url(self):
        if not self.best_oa_location:
            return None
        return self.best_oa_location.best_url

    @property
    def best_evidence(self):
        if not self.best_oa_location:
            return None
        return self.best_oa_location.display_evidence

    @property
    def best_oa_location_dict(self):
        best_location = self.best_oa_location
        if best_location:
            return best_location.to_dict_v2()
        return None

    @property
    def best_oa_location(self):
        all_locations = [location for location in self.all_oa_locations]
        if all_locations:
            return all_locations[0]
        return None

    @property
    def all_oa_locations(self):
        all_locations = [location for location in self.deduped_sorted_locations]
        if all_locations:
            for location in all_locations:
                location.is_best = False
            all_locations[0].is_best = True
        return all_locations

    def all_oa_location_dicts(self):
        return [location.to_dict_v2() for location in self.all_oa_locations]

    def to_dict(self):
        response = {
            "algorithm_version": self.data_standard,
            "doi_resolver": self.doi_resolver,
            "evidence": self.evidence,
            "free_fulltext_url": self.fulltext_url,
            "is_boai_license": self.is_boai_license,
            "is_free_to_read": self.is_free_to_read,
            "is_subscription_journal": self.is_subscription_journal,
            "license": self.license,
            "oa_color": self.oa_color,
            "reported_noncompliant_copies": self.reported_noncompliant_copies
            # "oa_color_v2": self.oa_status,
            # "year": self.year,
            # "found_hybrid": self.blue_locations != [],
            # "found_green": self.green_locations != [],
            # "issns": self.issns,
            # "version": self.version,
            # "_best_open_url": self.fulltext_url,
            # "_open_urls": self.open_urls,
            # "_closed_urls": self.closed_urls
        }

        for k in ["doi", "title", "url"]:
            value = getattr(self, k, None)
            if value:
                response[k] = value

        if self.error:
            response["error"] = self.error

        return response

    @property
    def best_location(self):
        if not self.deduped_sorted_locations:
            return None
        return self.deduped_sorted_locations[0]

    @property
    def is_archived_somewhere(self):
        if self.is_oa:
            return any([location.oa_color=="green" for location in self.deduped_sorted_locations])
        return None

    @property
    def oa_is_doaj_journal(self):
        if self.is_oa:
            if oa_local.is_open_via_doaj_issn(self.issns, self.year) or \
                oa_local.is_open_via_doaj_journal(self.all_journals, self.year):
                return True
            else:
                return False
        return False

    @property
    def oa_is_open_journal(self):
        if self.is_oa:
            return self.oa_is_doaj_journal
            # eventually add options here for when it is open but not in doaj
        return False

    @property
    def oa_host_type(self):
        if self.is_oa:
            return self.best_location.host_type
        return None

    @property
    def display_updated(self):
        if self.updated:
            return self.updated.isoformat()
        return None

    def to_dict_v2(self):
        response = {
            "doi": self.doi,
            "doi_url": self.url,
            "is_oa": self.is_oa,
            "best_oa_location": self.best_oa_location_dict,
            "oa_locations": self.all_oa_location_dicts(),
            "data_standard": self.data_standard,
            "title": self.best_title,
            "year": self.year,
            "journal_is_oa": self.oa_is_open_journal,
            "journal_is_in_doaj": self.oa_is_doaj_journal,
            "journal_issns": self.display_issns,
            "journal_name": self.journal,
            "publisher": self.publisher,
            "updated": self.display_updated,
            "genre": self.genre,
            "z_authors": self.authors,
            # "crossref_api_raw": self.crossref_api_raw,

            # need this one for Unpaywall
            "x_reported_noncompliant_copies": self.reported_noncompliant_copies,

            # "x_crossref_api_raw": self.crossref_api_raw

        }

        if self.error:
            response["x_error"] = True

        return response





# db.create_all()
# commit_success = safe_commit(db)
# if not commit_success:
#     logger.info(u"COMMIT fail making objects")
