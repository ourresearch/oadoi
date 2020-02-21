import datetime
import json
import os
from random import random
from time import sleep
from time import time

import requests
import shortuuid
from sickle import Sickle, oaiexceptions
from sickle.iterator import OAIItemIterator
from sickle.models import ResumptionToken
from sickle.oaiexceptions import NoRecordsMatch, BadArgument
from sickle.response import OAIResponse
from sqlalchemy import or_

import pmh_record
from app import db
from app import logger
from repository import Repository
from util import elapsed
from util import safe_commit


def lookup_endpoint_by_pmh_url(pmh_url_query=None):
    endpoints = Endpoint.query.filter(Endpoint.pmh_url.ilike(u"%{}%".format(pmh_url_query))).all()
    return endpoints


class Endpoint(db.Model):
    id = db.Column(db.Text, primary_key=True)
    id_old = db.Column(db.Text)
    repo_unique_id = db.Column(db.Text, db.ForeignKey(Repository.id))
    pmh_url = db.Column(db.Text)
    pmh_set = db.Column(db.Text)
    last_harvest_started = db.Column(db.DateTime)
    last_harvest_finished = db.Column(db.DateTime)
    most_recent_year_harvested = db.Column(db.DateTime)
    earliest_timestamp = db.Column(db.DateTime)
    email = db.Column(db.Text)  # to help us figure out what kind of repo it is
    error = db.Column(db.Text)
    repo_request_id = db.Column(db.Text)
    harvest_identify_response = db.Column(db.Text)
    harvest_test_recent_dates = db.Column(db.Text)
    sample_pmh_record = db.Column(db.Text)
    contacted = db.Column(db.DateTime)
    contacted_text = db.Column(db.Text)
    policy_promises_no_submitted = db.Column(db.Boolean)
    policy_promises_no_submitted_evidence = db.Column(db.Text)
    ready_to_run = db.Column(db.Boolean)
    metadata_prefix = db.Column(db.Text)
    retry_interval = db.Column(db.Interval)
    retry_at = db.Column(db.DateTime)

    meta = db.relationship(
        'Repository',
        lazy='subquery',
        cascade="all",
        backref=db.backref("endpoints", lazy="subquery")
    )

    def __init__(self, **kwargs):
        super(self.__class__, self).__init__(**kwargs)
        if not self.id:
            self.id = shortuuid.uuid()[0:20].lower()
        if not self.metadata_prefix:
            self.metadata_prefix = 'oai_dc'

    @property
    def repo(self):
        return self.meta

    def run_diagnostics(self):
        response = test_harvest_url(self.pmh_url)
        self.harvest_identify_response = response["harvest_identify_response"]
        # self.harvest_test_initial_dates = response["harvest_test_initial_dates"]
        self.harvest_test_recent_dates = response["harvest_test_recent_dates"]
        self.sample_pmh_record = response["sample_pmh_record"]

    def harvest(self):
        if not self.harvest_identify_response or not self.harvest_test_recent_dates:
            self.set_identify_and_initial_query()

        today = datetime.datetime.utcnow().date()
        tomorrow = today + datetime.timedelta(days=1)
        yesterday = today - datetime.timedelta(days=1)

        first = (self.most_recent_year_harvested or datetime.datetime(2000, 1, 1)).date()
        first = min(first, yesterday)

        if self.id_old in ['citeseerx.ist.psu.edu/oai2',
                           'europepmc.org/oai.cgi',
                           'www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi',
                           'www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi2']:
            first_plus_delta = first + datetime.timedelta(days=7)
        elif self.id == '4bd6f8f5107c0df6f48':
            first_plus_delta = first + datetime.timedelta(days=1)
        elif self.id == '0d27b133730393e00e1':
            first_plus_delta = first + datetime.timedelta(days=1)
        elif self.id == 'jmpfmmfru5pzhy4lbrdm':
            first_plus_delta = first + datetime.timedelta(days=1)
        elif self.id_old in ['export.arxiv.org/oai2']:
            first_plus_delta = first + datetime.timedelta(days=1)
        elif 'osti.gov/oai' in self.pmh_url:
            first_plus_delta = first + datetime.timedelta(days=1)
        elif 'share.osf.io' in self.pmh_url:
            first_plus_delta = first + datetime.timedelta(days=1)
        else:
            first_plus_delta = first + datetime.timedelta(days=7)

        last = min(first_plus_delta, tomorrow)

        # now do the harvesting
        self.call_pmh_endpoint(first=first, last=last)

        # if success, update so we start at next point next time
        base_retry_interval = datetime.timedelta(minutes=5)
        if self.error:
            logger.info(u"error so not saving finished info: {}".format(self.error))
            retry_interval = self.retry_interval or base_retry_interval
            self.retry_at = datetime.datetime.utcnow() + retry_interval
            self.retry_interval = retry_interval * 2
        else:
            logger.info(u"success!  saving info")
            self.last_harvest_finished = datetime.datetime.utcnow().isoformat()
            self.most_recent_year_harvested = min(yesterday, last)
            self.last_harvest_started = None
            self.retry_at = None
            self.retry_interval = base_retry_interval

    def get_pmh_record(self, record_id):
        my_sickle = _get_my_sickle(self.pmh_url)
        pmh_input_record = my_sickle.GetRecord(identifier=record_id, metadataPrefix=self.metadata_prefix)
        my_pmh_record = pmh_record.PmhRecord()
        my_pmh_record.populate(self.id, pmh_input_record)
        my_pmh_record.repo_id = self.id_old  # delete once endpoint_id is populated
        return my_pmh_record

    def set_identify_and_initial_query(self):
        if not self.pmh_url:
            self.harvest_identify_response = u"error, no pmh_url given"
            return

        my_sickle = None
        try:
            # set timeout quick... if it can't do this quickly, won't be good for harvesting
            logger.debug(u"getting my_sickle for {}".format(self))
            my_sickle = _get_my_sickle(self.pmh_url, timeout=10)
            my_sickle.Identify()
            self.harvest_identify_response = "SUCCESS!"

        except Exception as e:
            logger.exception(u"in set_identify_and_initial_query")
            self.error = u"error in calling identify: {} {}".format(
                e.__class__.__name__, unicode(e.message).encode("utf-8"))
            if my_sickle:
                self.error += u" calling {}".format(my_sickle.get_http_response_url())

            self.harvest_identify_response = self.error

        self.sample_pmh_record = None

        try:
            sample_pmh_record = self.get_recent_pmh_record()
            if sample_pmh_record:
                self.harvest_test_recent_dates = "SUCCESS!"
                self.sample_pmh_record = json.dumps(sample_pmh_record.metadata)
            else:
                self.harvest_test_recent_dates = "error, no pmh_input_records returned"
        except Exception as e:
            self.error = u"error in get_recent_pmh_record: {} {}".format(
                e.__class__.__name__, unicode(e.message).encode("utf-8"))
            self.harvest_test_recent_dates = self.error

    def get_recent_pmh_record(self):
        last = datetime.datetime.utcnow()
        first = last - datetime.timedelta(days=30)

        args = {'metadataPrefix': self.metadata_prefix}

        my_sickle = _get_my_sickle(self.pmh_url)
        logger.info(u"connected to sickle with {}".format(self.pmh_url))

        args['from'] = first.isoformat()[0:10]
        args["until"] = last.isoformat()[0:10]

        if self.pmh_set:
            args["set"] = self.pmh_set

        logger.info(u"calling ListIdentifiers with {} {}".format(self.pmh_url, args))
        try:
            pmh_identifiers = my_sickle.ListIdentifiers(ignore_deleted=True, **args)
            pmh_identifier = self.safe_get_next_record(pmh_identifiers)
            if pmh_identifier:
                return my_sickle.GetRecord(identifier=pmh_identifier.identifier, metadataPrefix=self.metadata_prefix)
            else:
                return None
        except NoRecordsMatch:
            logger.info(u"no records with {} {}".format(self.pmh_url, args))
            return None

    def get_pmh_input_record(self, first, last, use_date_default_format=True):
        args = {'metadataPrefix': self.metadata_prefix}
        pmh_records = []
        self.error = None

        my_sickle = _get_my_sickle(self.pmh_url)
        logger.info(u"connected to sickle with {}".format(self.pmh_url))

        args['from'] = first.isoformat()[0:10]
        if not use_date_default_format:
            args['from'] += "T00:00:00Z"

        if last:
            args["until"] = last.isoformat()[0:10]
            if not use_date_default_format:
                args['until'] += "T00:00:00Z"

        if self.pmh_set:
            args["set"] = self.pmh_set

        logger.info(u"calling ListRecords with {} {}".format(self.pmh_url, args))
        try:
            try:
                pmh_records = my_sickle.ListRecords(ignore_deleted=True, **args)
                pmh_input_record = self.safe_get_next_record(pmh_records)
            except NoRecordsMatch:
                logger.info(u"no records with {} {}".format(self.pmh_url, args))
                pmh_input_record = None
            except BadArgument as e:
                if use_date_default_format:
                    return self.get_pmh_input_record(first, last, use_date_default_format=False)
                else:
                    raise e
        except Exception as e:
            logger.exception(u"error with {} {}".format(self.pmh_url, args))
            pmh_input_record = None
            self.error = u"error in get_pmh_input_record: {} {}".format(
                e.__class__.__name__, unicode(e.message).encode("utf-8"))
            if my_sickle:
                self.error += u" calling {}".format(my_sickle.get_http_response_url())

        return pmh_input_record, pmh_records, self.error

    def call_pmh_endpoint(self,
                          first=None,
                          last=None,
                          chunk_size=50,
                          scrape=False):

        start_time = time()
        records_to_save = []
        num_records_updated = 0
        loop_counter = 0
        self.error = None

        (pmh_input_record, pmh_records, error) = self.get_pmh_input_record(first, last)

        if error:
            self.error = u"error in get_pmh_input_record: {}".format(error)
            return

        while pmh_input_record:
            loop_counter += 1
            # create the record
            my_pmh_record = pmh_record.PmhRecord()

            # set its vars
            my_pmh_record.repo_id = self.id_old  # delete once endpoint_ids are all populated
            my_pmh_record.rand = random()
            my_pmh_record.populate(self.id, pmh_input_record)

            if is_complete(my_pmh_record):
                my_pages = my_pmh_record.mint_pages()
                my_pmh_record.pages = my_pages
                if scrape:
                    for my_page in my_pages:
                        my_page.scrape_if_matches_pub()
                records_to_save.append(my_pmh_record)
                my_pmh_record.delete_old_record()
                db.session.merge(my_pmh_record)
            else:
                logger.info(u"pmh record is not complete")
                # print my_pmh_record
                pass

            if len(records_to_save) >= chunk_size:
                num_records_updated += len(records_to_save)
                safe_commit(db)
                records_to_save = []

            if loop_counter % 100 == 0:
                logger.info(u"iterated through 100 more items, loop_counter={} for {}".format(loop_counter, self.id))

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

        logger.info(u"updated {} PMH records for endpoint_id={}, took {} seconds".format(
            num_records_updated, self.id, elapsed(start_time, 2)))

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
        except Exception as e:
            logger.exception(u"misc exception!: {}  skipping".format(e))
            self.error = u"error in safe_get_next_record"
            return None
        return next_record

    def get_num_pmh_records(self):
        from pmh_record import PmhRecord
        num = db.session.query(PmhRecord.id).filter(PmhRecord.endpoint_id == self.id).count()
        return num

    def get_num_pages(self):
        from page import PageNew
        num = db.session.query(PageNew.id).filter(PageNew.endpoint_id == self.id).count()
        return num

    def get_num_open_with_dois(self):
        from page import PageNew
        num = db.session.query(PageNew.id).\
            distinct(PageNew.normalized_title).\
            filter(PageNew.endpoint_id == self.id).\
            filter(PageNew.num_pub_matches.isnot(None), PageNew.num_pub_matches >= 1).\
            filter(or_(PageNew.scrape_pdf_url.isnot(None), PageNew.scrape_metadata_url.isnot(None))).\
            count()
        return num

    def get_num_title_matching_dois(self):
        from page import PageNew
        num = db.session.query(PageNew.id).\
            distinct(PageNew.normalized_title).\
            filter(PageNew.endpoint_id == self.id).\
            filter(PageNew.num_pub_matches.isnot(None), PageNew.num_pub_matches >= 1).\
            count()
        return num

    def get_open_pages(self, limit=10):
        from page import PageNew
        pages = db.session.query(PageNew).\
            distinct(PageNew.normalized_title).\
            filter(PageNew.endpoint_id == self.id).\
            filter(PageNew.num_pub_matches.isnot(None), PageNew.num_pub_matches >= 1).\
            filter(or_(PageNew.scrape_pdf_url.isnot(None), PageNew.scrape_metadata_url.isnot(None))).\
            limit(limit).all()
        return [(p.id, p.url, p.normalized_title, p.pub.url, p.pub.unpaywall_api_url, p.scrape_version) for p in pages]

    def get_closed_pages(self, limit=10):
        from page import PageNew
        pages = db.session.query(PageNew).\
            distinct(PageNew.normalized_title).\
            filter(PageNew.endpoint_id == self.id).\
            filter(PageNew.num_pub_matches.isnot(None), PageNew.num_pub_matches >= 1).\
            filter(PageNew.scrape_updated.isnot(None), PageNew.scrape_pdf_url.is_(None), PageNew.scrape_metadata_url .is_(None)).\
            limit(limit).all()
        return [(p.id, p.url, p.normalized_title, p.pub.url, p.pub.unpaywall_api_url, p.scrape_updated) for p in pages]

    def get_num_pages_still_processing(self):
        from page import PageNew
        num = db.session.query(PageNew.id).filter(PageNew.endpoint_id == self.id, PageNew.num_pub_matches.is_(None)).count()
        return num

    def __repr__(self):
        return u"<Endpoint ( {} ) {}>".format(self.id, self.pmh_url)

    def to_dict(self):
        response = {
            "_endpoint_id": self.id,
            "_pmh_url": self.pmh_url,
            "num_pmh_records": self.get_num_pmh_records(),
            "num_pages": self.get_num_pages(),
            "num_open_with_dois": self.get_num_open_with_dois(),
            "num_title_matching_dois": self.get_num_title_matching_dois(),
            "num_pages_still_processing": self.get_num_pages_still_processing(),
            "pages_open": u"{}/debug/repo/{}/examples/open".format("http://localhost:5000", self.repo_unique_id),  # self.get_open_pages(),
            "pages_closed": u"{}/debug/repo/{}/examples/closed".format("http://localhost:5000", self.repo_unique_id),  # self.get_closed_pages(),
            "metadata": {}
        }

        if self.meta:
            response.update({
                "metadata": {
                    "home_page": self.repo.home_page,
                    "institution_name": self.repo.institution_name,
                    "repository_name": self.repo.repository_name
                }
            })
        return response

    def to_dict_status(self):
        response = {
            "results": {},
            "metadata": {}
        }

        for field in ["id", "repo_unique_id", "pmh_url", "email"]:
            response[field] = getattr(self, field)

        for field in ["harvest_identify_response", "harvest_test_recent_dates", "sample_pmh_record"]:
            response["results"][field] = getattr(self, field)

        if self.meta:
            for field in ["home_page", "institution_name", "repository_name"]:
                response["metadata"][field] = getattr(self.meta, field)

        return response

    def to_dict_repo_pulse(self):
        return {
            "metadata": {
                "endpoint_id": self.id,
                "repository_name": self.repo.repository_name,
                "institution_name": self.repo.institution_name,
                "pmh_url": self.pmh_url
            },
            "status": {
                "check0_identify_status": self.harvest_identify_response,
                "check1_query_status": self.harvest_test_recent_dates,
                "num_pmh_records": None,
                "last_harvest": self.most_recent_year_harvested,
                "num_pmh_records_matching_dois": None,
                "num_pmh_records_matching_dois_with_fulltext": None
            },
            "by_version_distinct_pmh_records_matching_dois": {}
        }


def test_harvest_url(pmh_url):
    response = {}
    temp_endpoint = Endpoint()
    temp_endpoint.pmh_url = pmh_url
    temp_endpoint.set_identify_and_initial_query()
    response["harvest_identify_response"] = temp_endpoint.harvest_identify_response
    response["sample_pmh_record"] = temp_endpoint.sample_pmh_record
    response["harvest_test_recent_dates"] = temp_endpoint.harvest_test_recent_dates

    return response


def is_complete(record):
    if not record.pmh_id:
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

    def get_complete_list_size(self):
        """Extract and store the resumptionToken from the last response."""
        resumption_token_element = self.oai_response.xml.find(
            './/' + self.sickle.oai_namespace + 'resumptionToken')
        if resumption_token_element is None:
            return None
        complete_list_size = resumption_token_element.attrib.get(
            'completeListSize', None)
        if complete_list_size:
            return int(complete_list_size)
        return complete_list_size


class OSTIOAIItemIterator(MyOAIItemIterator):
    def _next_response(self):
        """Get the next response from the OAI server.

        Copy-pasted from OAIItemIterator._next_response but adds metadataPrefix to params.
        """
        params = self.params
        if self.resumption_token:
            params = {
                'resumptionToken': self.resumption_token.token,
                'verb': self.verb,
                'metadataPrefix': params.get('metadataPrefix')
            }
        self.oai_response = self.sickle.harvest(**params)
        error = self.oai_response.xml.find(
            './/' + self.sickle.oai_namespace + 'error')
        if error is not None:
            code = error.attrib.get('code', 'UNKNOWN')
            description = error.text or ''
            try:
                raise getattr(
                    oaiexceptions, code[0].upper() + code[1:])(description)
            except AttributeError:
                raise oaiexceptions.OAIError(description)
        self.resumption_token = self._get_resumption_token()
        self._items = self.oai_response.xml.iterfind(
            './/' + self.sickle.oai_namespace + self.element)


def _get_my_sickle(repo_pmh_url, timeout=120):
    if not repo_pmh_url:
        return None

    proxy_url = None

    if any(fragment in repo_pmh_url for fragment in ["citeseerx"]):
        proxy_url = os.getenv("STATIC_IP_PROXY")
    elif any(fragment in repo_pmh_url for fragment in ["pure.coventry.ac.uk"]):
        proxy_url = os.getenv("VERY_STATIC_IP_PROXY")

    if proxy_url:
        proxies = {"https": proxy_url, "http": proxy_url}
    else:
        proxies = {}

    iterator = OSTIOAIItemIterator if 'osti.gov/oai' in repo_pmh_url else MyOAIItemIterator
    sickle = EuropePMCSickle if 'europepmc.org' in repo_pmh_url else MySickle
    my_sickle = sickle(repo_pmh_url, proxies=proxies, timeout=timeout, iterator=iterator)
    return my_sickle


# subclass so we can customize the number of retry seconds
class MySickle(Sickle):
    RETRY_SECONDS = 120

    def __init__(self, *args, **kwargs):
        self.http_response_url = None
        super(MySickle, self).__init__(*args, **kwargs)

    def get_http_response_url(self):
        if hasattr(self, "http_response_url"):
            return self.http_response_url
        return None

    def _massage_http_response(self, http_response):
        return http_response

    def harvest(self, **kwargs):  # pragma: no cover
        """Make HTTP requests to the OAI server.
        :param kwargs: OAI HTTP parameters.
        :rtype: :class:`sickle.OAIResponse`
        """
        start_time = time()
        for _ in range(self.max_retries):
            if self.http_method == 'GET':
                payload_str = "&".join("%s=%s" % (k, v) for k, v in kwargs.items())
                url_without_encoding = u"{}?{}".format(self.endpoint, payload_str)
                http_response = requests.get(url_without_encoding,
                                             **self.request_args)
                self.http_response_url = http_response.url
            else:
                http_response = requests.post(self.endpoint, data=kwargs,
                                              **self.request_args)
                self.http_response_url = http_response.url
            if http_response.status_code == 503:
                retry_after = self.RETRY_SECONDS
                logger.info("HTTP 503! Retrying after %d seconds..." % retry_after)
                sleep(retry_after)
            else:
                logger.info("took {} seconds to call pmh url: {}".format(elapsed(start_time), http_response.url))

                http_response = self._massage_http_response(http_response)

                http_response.raise_for_status()
                if self.encoding:
                    http_response.encoding = self.encoding
                return OAIResponse(http_response, params=kwargs)


class EuropePMCSickle(MySickle):
    def _massage_http_response(self, http_response):
        # server returns a 404 with NoRecordsMatch responses
        # treat this as a successful http request and handle the OAI-PMH error further up the stack
        if http_response.status_code == 404:
            http_response.status_code = 200

        return http_response
