import os
import re
from sickle import Sickle
from sickle.response import OAIResponse
from sickle.iterator import OAIItemIterator
from sickle.models import ResumptionToken
import requests
from time import sleep
from time import time
import datetime
from random import random
import argparse
import lxml
from sqlalchemy import or_

from app import db
from app import logger
import pmh_record
import pub
from util import elapsed
from util import safe_commit

def get_repos_by_ids(ids):
    repos = db.session.query(Repository).filter(Repository.id.in_(ids)).all()
    return repos

def lookup_repo_by_pmh_url(pmh_url_query=None):
    repos = Endpoint.query.filter(Endpoint.pmh_url.ilike(u"%{}%".format(pmh_url_query))).all()
    return repos

def get_sources_data(query_string=None):
    response = get_repository_data(query_string) + get_journal_data(query_string)
    return response

def get_sources_data_fast():
    all_journals = JournalMetadata.query.all()
    all_repos = Repository.query.all()
    all_sources = all_journals + all_repos

    return all_sources

    # all_sources_dict = {}
    # for source in all_sources:
    #     all_sources_dict[source.dedup_name] = source
    #
    # return all_sources_dict.values()


def get_journal_data(query_string=None):
    journal_meta_query = JournalMetadata.query
    if query_string:
        journal_meta_query = journal_meta_query.filter(or_(
            JournalMetadata.journal.ilike(u"%{}%".format(query_string)),
            JournalMetadata.publisher.ilike(u"%{}%".format(query_string)))
        )
    journal_meta = journal_meta_query.all()
    return journal_meta

def get_raw_repo_meta(query_string=None):
    raw_repo_meta_query = Repository.query.distinct(Repository.repository_name, Repository.institution_name)
    if query_string:
        raw_repo_meta_query = raw_repo_meta_query.filter(or_(
            Repository.repository_name.ilike(u"%{}%".format(query_string)),
            Repository.institution_name.ilike(u"%{}%".format(query_string)),
            Repository.home_page.ilike(u"%{}%".format(query_string)),
            Repository.id.ilike(u"%{}%".format(query_string))
        ))
    raw_repo_meta = raw_repo_meta_query.all()
    return raw_repo_meta

def get_repository_data(query_string=None):
    raw_repo_meta = get_raw_repo_meta(query_string)
    block_word_list = [
        "journal",
        "jurnal",
        "review",
        "revista",
        "annals",
        "annales",
        "magazine",
        "conference",
        "proceedings",
        "anales",
        "publisher",
        "press",
        "ojs",
        "bulletin",
        "acta"
    ]
    good_repo_meta = []
    for repo_meta in raw_repo_meta:
        if repo_meta.repository_name and repo_meta.institution_name:
            good_repo = True
            if repo_meta.bad_data:
                good_repo = False
            if repo_meta.is_journal:
                good_repo = False
            for block_word in block_word_list:
                if block_word in repo_meta.repository_name.lower() \
                        or block_word in repo_meta.institution_name.lower() \
                        or block_word in repo_meta.home_page.lower():
                    good_repo = False
                for endpoint in repo_meta.endpoints:
                    if block_word in endpoint.pmh_url.lower():
                        good_repo = False
            if good_repo:
                good_repo_meta.append(repo_meta)
    return good_repo_meta


# created using this:
#     create table journal_metadata as (
#         select distinct on (normalize_title_v2(journal_name), normalize_title_v2(publisher))
#         journal_name as journal, publisher, journal_issns as issns from export_main_no_versions_20180116 where genre = 'journal-article')
# delete from journal_metadata where publisher='CrossRef Test Account'
class JournalMetadata(db.Model):
    publisher = db.Column(db.Text, primary_key=True)
    journal = db.Column(db.Text, primary_key=True)
    issns = db.Column(db.Text)

    @property
    def text_for_comparision(self):
        response = ""
        for attr in ["publisher", "journal"]:
            value = getattr(self, attr)
            if not value:
                value = ""
            response += value.lower()
        return response

    @property
    def dedup_name(self):
        return self.publisher.lower() + " " + self.journal.lower()

    @property
    def home_page(self):
        if self.issns:
            issn = self.issns.split(",")[0]
        else:
            issn = ""
        url = u"https://www.google.com/search?q={}+{}".format(self.journal, issn)
        url = url.replace(u" ", u"+")
        return url

    def to_csv_row(self):
        row = []
        for attr in ["home_page", "publisher", "journal"]:
            value = getattr(self, attr)
            if not value:
                value = ""
            value = value.replace(",", "; ")
            row.append(value)
        csv_row = u",".join(row)
        return csv_row

    def __repr__(self):
        return u"<JournalMetadata ({} {})>".format(self.journal, self.publisher)

    def to_dict(self):
        response = {
            "home_page": self.home_page,
            "institution_name": self.publisher,
            "repository_name": self.journal
        }
        return response



class Repository(db.Model):
    id = db.Column(db.Text, db.ForeignKey('endpoint.repo_unique_id'), primary_key=True)
    home_page = db.Column(db.Text)
    institution_name = db.Column(db.Text)
    repository_name = db.Column(db.Text)
    error_raw = db.Column(db.Text)
    bad_data = db.Column(db.Text)
    is_journal = db.Column(db.Boolean)

    endpoints = db.relationship(
        'Endpoint',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("meta", lazy="subquery"),
        foreign_keys="Endpoint.repo_unique_id"
    )

    @property
    def text_for_comparision(self):
        return self.home_page.lower() + self.repository_name.lower() + self.institution_name.lower() + self.id.lower()

    @property
    def dedup_name(self):
        return self.institution_name.lower() + " " + self.repository_name.lower()

    def __repr__(self):
        return u"<Repository ({})>".format(self.id)

    def to_csv_row(self):
        row = []
        for attr in ["home_page", "institution_name", "repository_name"]:
            value = getattr(self, attr)
            if not value:
                value = ""
            value = value.replace(",", "; ")
            row.append(value)
        csv_row = u",".join(row)
        return csv_row

    def to_dict(self):
        response = {
            # "id": self.id,
            "home_page": self.home_page,
            "institution_name": self.institution_name,
            "repository_name": self.repository_name
            # "pmh_url": self.endpoint.pmh_url,
        }
        return response


class Endpoint(db.Model):
    id = db.Column(db.Text, primary_key=True)
    repo_unique_id = db.Column(db.Text, db.ForeignKey('repository.id'))
    name = db.Column(db.Text)
    pmh_url = db.Column(db.Text)
    pmh_set = db.Column(db.Text)
    last_harvest_started = db.Column(db.DateTime)
    last_harvest_finished = db.Column(db.DateTime)
    most_recent_year_harvested = db.Column(db.DateTime)
    earliest_timestamp = db.Column(db.DateTime)
    email = db.Column(db.Text)  # to help us figure out what kind of repo it is
    error = db.Column(db.Text)


    def __init__(self, **kwargs):
        super(self.__class__, self).__init__(**kwargs)

    def harvest(self):
        first = self.most_recent_year_harvested

        if not first:
            first = datetime.datetime(2000, 01, 01, 0, 0)

        if first > (datetime.datetime.utcnow() - datetime.timedelta(days=2)):
            first = datetime.datetime.utcnow() - datetime.timedelta(days=2)

        if self.id in ['citeseerx.ist.psu.edu/oai2',
                       'europepmc.org/oai.cgi',
                       'export.arxiv.org/oai2',
                       'www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi',
                       'www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi2']:
            first_plus_delta = first + datetime.timedelta(days=7)
        else:
            first_plus_delta = first.replace(year=first.year + 1)

        tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        last = min(first_plus_delta, tomorrow)
        first = first - datetime.timedelta(days=1)

        # now do the harvesting
        self.call_pmh_endpoint(first=first, last=last)

        # if success, update so we start at next point next time
        if self.error:
            logger.info(u"error so not saving finished info: {}".format(self.error))
        else:
            logger.info(u"success!  saving info")
            self.last_harvest_finished = datetime.datetime.utcnow().isoformat()
            self.most_recent_year_harvested = last
            self.last_harvest_started = None



    def get_my_sickle(self, repo_pmh_url, timeout=120):
        proxies = {}
        if "citeseerx" in repo_pmh_url:
            proxy_url = os.getenv("STATIC_IP_PROXY")
            proxies = {"https": proxy_url, "http": proxy_url}
        my_sickle = MySickle(repo_pmh_url, proxies=proxies, timeout=timeout, iterator=MyOAIItemIterator)
        return my_sickle

    def get_pmh_record(self, record_id):
        my_sickle = self.get_my_sickle(self.pmh_url)
        pmh_input_record = my_sickle.GetRecord(identifier=record_id, metadataPrefix="oai_dc")
        my_pmh_record = pmh_record.PmhRecord()
        my_pmh_record.populate(pmh_input_record)
        my_pmh_record.repo_id = self.id
        return my_pmh_record

    def set_repo_info(self):
        self.error = ""

        try:
            # set timeout quick... if it can't do this quickly, won't be good for harvesting
            my_sickle = self.get_my_sickle(self.pmh_url, timeout=10)
            data = my_sickle.Identify()

        except AttributeError:
            self.error += u"AttributeError in set_repo_info."
            return
        except requests.exceptions.RequestException as e:
            self.error += u"RequestException in set_repo_info: {}".format(unicode(e.message).encode("utf-8"))
            return
        except lxml.etree.XMLSyntaxError as e:
            self.error += u"XMLSyntaxError in set_repo_info: {}".format(unicode(e.message).encode("utf-8"))
            return
        except Exception as e:
            logger.exception(u"in set_repo_info")
            self.error += u"Other exception in set_repo_info: {}".format(unicode(e.message).encode("utf-8"))
            return

        try:
            self.name = data.repositoryName
        except AttributeError:
            self.error += u"Error setting name from Identify call."
            self.name = self.id
            pass

        try:
            self.email = data.adminEmail
        except AttributeError:
            pass

        try:
            self.earliest_timestamp = data.earliestDatestamp
        except AttributeError:
            pass

    def call_pmh_endpoint(self,
                          first=None,
                          last=None,
                          chunk_size=50,
                          scrape=False):

        start_time = time()
        args = {}
        args['metadataPrefix'] = 'oai_dc'

        my_sickle = self.get_my_sickle(self.pmh_url)
        logger.info(u"connected to sickle with {}".format(self.pmh_url))

        args['from'] = first.isoformat()[0:10]
        if last:
            args["until"] = last.isoformat()[0:10]

        if self.pmh_set:
            args["set"] = self.pmh_set

        records_to_save = []
        num_records_updated = 0
        loop_counter = 0

        logger.info(u"calling ListRecords with {} {}".format(self.pmh_url, args))
        try:
            pmh_records = my_sickle.ListRecords(ignore_deleted=True, **args)
            # logger.info(u"got pmh_records with {} {}".format(self.pmh_url, args))
            pmh_input_record = self.safe_get_next_record(pmh_records)
        except Exception as e:
            logger.exception(u"no records with {} {}".format(self.pmh_url, args))
            # logger.exception(u"no records with {} {}".format(self.pmh_url, args))
            pmh_input_record = None

        while pmh_input_record:
            loop_counter += 1
            # create the record
            my_pmh_record = pmh_record.PmhRecord()

            # set its vars
            my_pmh_record.repo_id = self.id
            my_pmh_record.rand = random()
            my_pmh_record.populate(pmh_input_record)

            if is_complete(my_pmh_record):
                my_pages = my_pmh_record.mint_pages()
                my_pmh_record.pages = my_pages
                # logger.info(u"made {} pages for id {}: {}".format(len(my_pages), my_pmh_record.id, [p.url for p in my_pages]))
                if scrape:
                    for my_page in my_pages:
                        my_page.scrape_if_matches_pub()
                records_to_save.append(my_pmh_record)
                db.session.merge(my_pmh_record)
                # logger.info(u"my_pmh_record {}".format(my_pmh_record))
            else:
                # logger.info(u"pmh record is not complete")
                pass

            if len(records_to_save) >= chunk_size:
                num_records_updated += len(records_to_save)
                last_record = records_to_save[-1]
                # logger.info(u"last record saved: {} for {}".format(last_record.id, self.id))
                safe_commit(db)
                records_to_save = []

            if loop_counter % 100 == 0:
                logger.info(u"iterated through 100 more items, loop_counter={}".format(loop_counter))

            pmh_input_record = self.safe_get_next_record(pmh_records)

        # make sure to get the last ones
        if records_to_save:
            num_records_updated += len(records_to_save)
            last_record = records_to_save[-1]
            logger.info(u"saving {} last ones, last record saved: {} for {}, loop_counter={}".format(
                len(records_to_save), last_record.id, self.id, loop_counter))
            safe_commit(db)
        else:
            logger.info(u"finished loop, but no records to save, loop_counter={}".format(loop_counter))

        # if num_records_updated > 0:
        if True:
            logger.info(u"updated {} PMH records for repo_id={}, starting on {}, took {} seconds".format(
                num_records_updated, self.id, args['from'], elapsed(start_time, 2)))


    def safe_get_next_record(self, current_record):
        self.error = None
        try:
            next_record = current_record.next()
        except (requests.exceptions.HTTPError, requests.exceptions.SSLError):
            logger.info(u"requests exception!  skipping")
            self.error = u"requests error in safe_get_next_record; try again"
            return None
        except (KeyboardInterrupt, SystemExit):
            # done
            return None
        except StopIteration:
            logger.info(u"stop iteration! stopping")
            return None
        except Exception:
            logger.exception(u"misc exception!  skipping")
            self.error = u"error in safe_get_next_record; try again"
            return None
        return next_record

    def get_num_pmh_records(self):
        from pmh_record import PmhRecord
        num = db.session.query(PmhRecord.id).filter(PmhRecord.repo_id==self.id).count()
        return num

    def get_num_pages(self):
        from page import PageNew
        num = db.session.query(PageNew.id).filter(PageNew.repo_id==self.id).count()
        return num

    def get_num_title_matching_dois(self):
        from page import PageNew
        num = db.session.query(PageNew.id).\
            distinct(PageNew.normalized_title).\
            filter(PageNew.repo_id==self.id).\
            filter(PageNew.num_pub_matches != None, PageNew.num_pub_matches > 1).\
            filter(or_(PageNew.scrape_pdf_url != None, PageNew.scrape_metadata_url != None)).\
            count()
        return num

    def get_open_pages(self, limit=5):
        from page import PageNew
        pages = db.session.query(PageNew).\
            distinct(PageNew.normalized_title).\
            filter(PageNew.repo_id==self.id).\
            filter(PageNew.num_pub_matches != None, PageNew.num_pub_matches > 1).\
            filter(or_(PageNew.scrape_pdf_url != None, PageNew.scrape_metadata_url != None)).\
            limit(limit).all()
        return [(p.id, p.url, p.normalized_title, p.pub.url, p.pub.unpaywall_api_url) for p in pages]

    def get_closed_pages(self, limit=5):
        from page import PageNew
        pages = db.session.query(PageNew).\
            distinct(PageNew.normalized_title).\
            filter(PageNew.repo_id==self.id).\
            filter(PageNew.num_pub_matches != None, PageNew.num_pub_matches > 1).\
            filter(PageNew.scrape_updated != None, PageNew.scrape_pdf_url == None, PageNew.scrape_metadata_url == None).\
            limit(limit).all()
        return [(p.id, p.url, p.normalized_title, p.pub.url, p.pub.unpaywall_api_url) for p in pages]

    def get_num_pages_still_processing(self):
        from page import PageNew
        num = db.session.query(PageNew.id).filter(PageNew.repo_id==self.id, PageNew.num_pub_matches == None).count()
        return num

    def __repr__(self):
        return u"<Endpoint {} ( {} ) {}>".format(self.name, self.id, self.pmh_url)


    def to_dict(self):
        response = {
            "_repo_id": self.id,
            "_pmh_url": self.pmh_url,
            "num_pmh_records": self.get_num_pmh_records(),
            "num_pages": self.get_num_pages(),
            "num_title_matching_dois": self.get_num_title_matching_dois(),
            "num_pages_still_processing": self.get_num_pages_still_processing(),
            "pages_open": self.get_open_pages(),
            "pages_closed": self.get_closed_pages(),
            "metadata": {}
        }

        if self.meta:
            response.update({
                "metadata": {
                    "home_page": self.meta.home_page,
                    "institution_name": self.meta.institution_name,
                    "repository_name": self.meta.repository_name
                }
            })
        return response




def is_complete(record):
    if not record.id:
        return False
    if not record.title:
        return False
    if not record.urls:
        return False

    if record.oa == "0":
        logger.info(u"record {} is closed access. skipping.".format(record["id"]))
        return False

    return True









class MyOAIItemIterator(OAIItemIterator):
    def _get_resumption_token(self):
        """Extract and store the resumptionToken from the last response."""
        resumption_token_element = self.oai_response.xml.find(
            './/' + self.sickle.oai_namespace + 'resumptionToken')
        if resumption_token_element is None:
            return None
        token = resumption_token_element.text
        cursor = resumption_token_element.attrib.get('cursor', None)
        complete_list_size = resumption_token_element.attrib.get(
            'completeListSize', None)
        expiration_date = resumption_token_element.attrib.get(
            'expirationDate', None)
        resumption_token = ResumptionToken(
            token=token, cursor=cursor,
            complete_list_size=complete_list_size,
            expiration_date=expiration_date
        )
        return resumption_token


# subclass so we can customize the number of retry seconds
class MySickle(Sickle):
    RETRY_SECONDS = 120
    def harvest(self, **kwargs):  # pragma: no cover
        """Make HTTP requests to the OAI server.
        :param kwargs: OAI HTTP parameters.
        :rtype: :class:`sickle.OAIResponse`
        """
        start_time = time()
        for _ in range(self.max_retries):
            if self.http_method == 'GET':
                payload_str = "&".join("%s=%s" % (k,v) for k,v in kwargs.items())
                url_without_encoding = u"{}?{}".format(self.endpoint, payload_str)
                http_response = requests.get(url_without_encoding,
                                             **self.request_args)
            else:
                http_response = requests.post(self.endpoint, data=kwargs,
                                              **self.request_args)
            if http_response.status_code == 503:
                retry_after = self.RETRY_SECONDS
                logger.info("HTTP 503! Retrying after %d seconds..." % retry_after)
                sleep(retry_after)
            else:
                logger.info("took {} seconds to call pmh url: {}".format(elapsed(start_time), http_response.url))

                http_response.raise_for_status()
                if self.encoding:
                    http_response.encoding = self.encoding
                return OAIResponse(http_response, params=kwargs)


