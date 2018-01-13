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

from app import db
from app import logger
import pmh_record
import pub
from util import elapsed
from util import safe_commit


class Repository(db.Model):
    id = db.Column(db.Text, primary_key=True)
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

        if self.id in ['citeseerx.ist.psu.edu/oai2', 'europepmc.org/oai.cgi', 'export.arxiv.org/oai2', 'www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi']:
            first_plus_delta = first + datetime.timedelta(days=7)
        else:
            first_plus_delta = first.replace(year=first.year + 1)

        tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        last = min(first_plus_delta, tomorrow)
        first = first - datetime.timedelta(days=1)

        # now do the harvesting
        # self.call_pmh_endpoint(first=first, last=last)

        # fix this.  just like this for debugging
        self.call_pmh_endpoint(first=first, last=first)

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
            logger.info(u"no records with {} {}".format(self.pmh_url, args))
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

    def __repr__(self):
        return u"<Repository {} ( {} ) {}>".format(self.name, self.id, self.pmh_url)





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


