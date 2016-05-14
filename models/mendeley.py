from __future__ import absolute_import

# need to get system mendeley library
from mendeley.exception import MendeleyException
import mendeley as mendeley_lib

from util import remove_punctuation
import os
import requests

mendeley_session = None

def get_mendeley_session():
    a = requests.adapters.HTTPAdapter(pool_connections = 150, pool_maxsize = 150)

    mendeley_client = mendeley_lib.Mendeley(
        client_id=os.getenv("MENDELEY_OAUTH2_CLIENT_ID"),
        client_secret=os.getenv("MENDELEY_OAUTH2_SECRET"))
    auth = mendeley_client.start_client_credentials_flow()
    session = auth.authenticate()
    return session

def set_mendeley_data(product):
    global mendeley_session

    if not mendeley_session:
        mendeley_session = get_mendeley_session()

    resp = None
    try:
        biblio_title = remove_punctuation(product.title).lower()
        biblio_year = product.year
        if biblio_title and biblio_year:
            try:
                doc = mendeley_session.catalog.advanced_search(
                        title=biblio_title,
                        min_year=biblio_year,
                        max_year=biblio_year,
                        view='stats').list(page_size=1).items[0]
            except (UnicodeEncodeError, IndexError):
                biblio_title = remove_punctuation(product.title.encode('ascii','ignore'))
                try:
                    doc = mendeley_session.catalog.advanced_search(
                            title=biblio_title,
                            min_year=biblio_year,
                            max_year=biblio_year,
                            view='stats').list(page_size=1).items[0]
                except (IndexError):
                    return None

            mendeley_title = remove_punctuation(doc.title).lower()
            if biblio_title == mendeley_title:
                # print u"\nMatch! got the mendeley paper! for title {}".format(biblio_title)
                print "got mendeley for {}".format(product.id)
                resp = {}
                resp["reader_count"] = doc.reader_count
                resp["reader_count_by_academic_status"] = doc.reader_count_by_academic_status
                resp["reader_count_by_subdiscipline"] = doc.reader_count_by_subdiscipline
                resp["reader_count_by_country"] = doc.reader_count_by_country
                resp["mendeley_url"] = doc.link
                resp["abstract"] = doc.abstract
            else:
                # print u"didn't find {}".format(biblio_title)
                # print u"Mendeley: titles don't match so not using this match \n%s and \n%s" %(
                #     biblio_title, mendeley_title)
                resp = None
    except (KeyError, MendeleyException):
        # logger.info(u"No biblio found in _get_doc_by_title")
        pass

    # if doc:
        # try:
        #     drilldown_url = doc.link
        #     metrics_and_drilldown["mendeley:readers"] = (doc.reader_count, drilldown_url)
        #     metrics_and_drilldown["mendeley:career_stage"] = (doc.reader_count_by_academic_status, drilldown_url)
        #
        #     by_discipline = {}
        #     by_subdiscipline = doc.reader_count_by_subdiscipline
        #     if by_subdiscipline:
        #         for discipline, subdiscipline_breakdown in by_subdiscipline.iteritems():
        #             by_discipline[discipline] = sum(subdiscipline_breakdown.values())
        #         metrics_and_drilldown["mendeley:discipline"] = (by_discipline, drilldown_url)
        #
        #     by_country_iso = {}
        #     by_country_names = doc.reader_count_by_country
        #     if by_country_names:
        #         for country_name, country_breakdown in by_country_names.iteritems():
        #             iso = iso_code_from_name(country_name)
        #             if iso:
        #                 by_country_iso[iso] = country_breakdown
        #             else:
        #                 logger.error(u"Can't find country {country} in lookup".format(
        #                     country=country_name))
        #         if by_country_iso:
        #             metrics_and_drilldown["mendeley:countries"] = (by_country_iso, drilldown_url)
        #
        # except KeyError:
        #     pass

    return resp




