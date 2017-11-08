import os
from sickle import Sickle
from sickle.response import OAIResponse
import requests
from time import sleep
import argparse

from app import db
from app import logger
import pmh_record
import pub
from util import safe_commit
from util import elapsed
from util import is_doi_url
from util import clean_doi
from util import NoDoiException


class Repository(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    pmh_url = db.Column(db.Text)
    last_harvest_started = db.Column(db.DateTime)
    most_recent_year_harvested = db.Column(db.DateTime)
    most_recent_day_harvested = db.Column(db.DateTime)


    def __init__(self, **kwargs):
        super(self.__class__, self).__init__(**kwargs)

    def pmh_to_db(self,
                  first=None,
                  last=None,
                  chunk_size=10,
                  scrape=False):


        args = {}
        args['metadataPrefix'] = 'oai_dc'

        if "citeseerx" in self.pmh_url:
            proxy_url = os.getenv("STATIC_IP_PROXY")
            proxies = {"https": proxy_url, "http": proxy_url}
        else:
            proxies = {}

        my_sickle = MySickle(self.pmh_url, proxies=proxies, timeout=120)
        logger.info(u"connected to sickle with {} {}".format(self.pmh_url, proxies))


        args['from'] = first
        if last:
            args["until"] = last

        records_to_save = []

        logger.info(u"calling ListRecords with {} {}".format(self.pmh_url, args))
        try:
            pmh_records = my_sickle.ListRecords(ignore_deleted=True, **args)
            logger.info(u"got pmh_records with {} {}".format(self.pmh_url, args))
            pmh_input_record = safe_get_next_record(pmh_records)
        except Exception as e:
            logger.info(u"no records with {} {}".format(self.pmh_url, args))
            # logger.exception(u"no records with {} {}".format(self.pmh_url, args))
            pmh_input_record = None

        while pmh_input_record:

            my_pmh_record = pmh_record.PmhRecord()

            my_pmh_record.id = pmh_input_record.header.identifier
            my_pmh_record.api_raw = pmh_input_record.raw
            my_pmh_record.record_timestamp = pmh_input_record.header.datestamp
            my_pmh_record.title = oai_tag_match("title", pmh_input_record)
            my_pmh_record.authors = oai_tag_match("creator", pmh_input_record, return_list=True)
            my_pmh_record.oa = oai_tag_match("oa", pmh_input_record)
            my_pmh_record.urls = oai_tag_match("identifier", pmh_input_record, return_list=True)
            for fulltext_url in my_pmh_record.urls:
                if fulltext_url and (is_doi_url(fulltext_url) or fulltext_url.startswith(u"doi:")):
                    try:
                        my_pmh_record.doi = clean_doi(fulltext_url)
                    except NoDoiException:
                        pass

            my_pmh_record.license = oai_tag_match("rights", pmh_input_record)
            my_pmh_record.relations = oai_tag_match("relation", pmh_input_record, return_list=True)
            my_pmh_record.sources = oai_tag_match("collname", pmh_input_record, return_list=True)
            my_pmh_record.source = self.id

            # print pmh_record

            if is_complete(my_pmh_record):
                my_pages = my_pmh_record.mint_pages()
                print u"made {} pages for id {}".format(len(my_pages), my_pmh_record.id)
                if scrape:
                    print u"scraping pages"
                    for my_page in my_pages:
                        my_page.scrape()
                    print "done"

                db.session.merge(my_pmh_record)
                records_to_save.append(my_pmh_record)
                logger.info(u":")
                print u"my_pmh_record {}".format(my_pmh_record.get_good_urls())
            else:
                print "not complete"

            if len(records_to_save) >= chunk_size:
                last_record = records_to_save[-1]
                logger.info(u"last record saved: {} for {}".format(last_record.id, self.id))
                safe_commit(db)
                records_to_save = []

            pmh_input_record = safe_get_next_record(pmh_records)

        # make sure to get the last ones
        if records_to_save:
            last_record = records_to_save[-1]
            logger.info(u"saving {} last ones, last record saved: {} for {}".format(len(records_to_save), last_record.id, self.id))
            safe_commit(db)
        logger.info(u"done everything for {}".format(self.id))


    def __repr__(self):
        return u"<Repository {} ( {} ) {}>".format(self.name, self.id, self.pmh_url)



def oai_tag_match(tagname, record, return_list=False):
    if not tagname in record.metadata:
        return None
    matches = record.metadata[tagname]
    if return_list:
        return matches  # will be empty list if we found naught
    else:
        try:
            return matches[0]
        except IndexError:  # no matches.
            return None


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



def safe_get_next_record(records):
    try:
        next_record = records.next()
    except (requests.exceptions.HTTPError, requests.exceptions.SSLError):
        logger.info(u"requests exception!  skipping")
        return safe_get_next_record(records)
    except (KeyboardInterrupt, SystemExit):
        # done
        return None
    except StopIteration:
        # logger.info(u"stop iteration! stopping")
        return None
    except Exception:
        logger.exception(u"misc exception!  skipping")
        return safe_get_next_record(records)
    return next_record






# subclass so we can customize the number of retry seconds
class MySickle(Sickle):
    RETRY_SECONDS = 3
    def harvest(self, **kwargs):  # pragma: no cover
        """Make HTTP requests to the OAI server.
        :param kwargs: OAI HTTP parameters.
        :rtype: :class:`sickle.OAIResponse`
        """
        for _ in range(self.max_retries):
            if self.http_method == 'GET':
                http_response = requests.get(self.endpoint, params=kwargs,
                                             **self.request_args)
            else:
                http_response = requests.post(self.endpoint, data=kwargs,
                                              **self.request_args)
            if http_response.status_code == 503:
                retry_after = self.RETRY_SECONDS
                logger.info(
                    "HTTP 503! Retrying after %d seconds..." % retry_after)
                sleep(retry_after)
            else:
                http_response.raise_for_status()
                if self.encoding:
                    http_response.encoding = self.encoding
                return OAIResponse(http_response, params=kwargs)


