from __future__ import absolute_import

# need to get system mendeley library
from mendeley.exception import MendeleyException
import mendeley as mendeley_lib

from util import remove_punctuation
import os


def get_mendeley_session():
    mendeley_client = mendeley_lib.Mendeley(
        client_id=os.getenv("MENDELEY_OAUTH2_CLIENT_ID"),
        client_secret=os.getenv("MENDELEY_OAUTH2_SECRET"))
    auth = mendeley_client.start_client_credentials_flow()
    session = auth.authenticate()
    return session

def set_mendeley_data(product):

    if product.mendeley_api_raw:
        return

    resp = None
    doc = None

    try:
        mendeley_session = get_mendeley_session()
        if product.doi:
            method = "doi"
            doc = mendeley_session.catalog.by_identifier(
                    doi=product.doi,
                    view='stats')

        if not doc:
            biblio_title = remove_punctuation(product.title).lower()
            biblio_year = product.year
            if biblio_title and biblio_year:
                try:
                    method = "title"
                    doc = mendeley_session.catalog.advanced_search(
                            title=biblio_title,
                            min_year=biblio_year,
                            max_year=biblio_year,
                            view='stats').list(page_size=1).items[0]
                except (UnicodeEncodeError, IndexError):
                    biblio_title = remove_punctuation(product.title.encode('ascii','ignore'))
                    try:
                        method = "unicode title"
                        doc = mendeley_session.catalog.advanced_search(
                                title=biblio_title,
                                min_year=biblio_year,
                                max_year=biblio_year,
                                view='stats').list(page_size=1).items[0]
                    except (IndexError):
                        return None
                mendeley_title = remove_punctuation(doc.title).lower()
                if biblio_title != mendeley_title:
                    return None

        if not doc:
            return None

        # print u"\nMatch! got the mendeley paper! for title {}".format(biblio_title)
        print "got mendeley for {} using {}".format(product.id, method)
        resp = {}
        resp["reader_count"] = doc.reader_count
        resp["reader_count_by_academic_status"] = doc.reader_count_by_academic_status
        resp["reader_count_by_subdiscipline"] = doc.reader_count_by_subdiscipline
        resp["reader_count_by_country"] = doc.reader_count_by_country
        resp["mendeley_url"] = doc.link
        resp["abstract"] = doc.abstract
        resp["method"] = method

    except (KeyError, MendeleyException):
        pass

    return resp




