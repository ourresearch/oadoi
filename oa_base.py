import os
import re
import datetime
import sys
import requests
import random
from time import time
from Levenshtein import ratio
from collections import defaultdict
from HTMLParser import HTMLParser
from sqlalchemy import sql
from sqlalchemy import text

from app import db
from webpage import WebpageInOpenRepo
from webpage import WebpageInUnknownRepo
from webpage import WebpageInClosedRepo
from oa_local import find_normalized_license
from util import elapsed
from util import normalize
from util import remove_punctuation


DEBUG_BASE = False
RESCRAPE_IN_CALL = False



def get_fulltext_webpages_from_our_base_doc(doc):
    response = []

    license = doc.get("fulltext_license", None)

    # workaround for a bug there was in the normalized license
    license_string_in_doc = doc.get("license", "")
    if license_string_in_doc:
        if "orks not in the public domain" in license_string_in_doc:
            license = None
        if not license:
            license = find_normalized_license(license_string_in_doc)



    # if doc["oa"]==2 and not "fulltext_url_dicts" in doc:
    # if True:
    #     base_result_obj = BaseResult(doc)
    #     base_result_obj.scrape_for_fulltext()
    #     base_result_obj.update_doc()
    #     doc = base_result_obj.doc



    if "fulltext_url_dicts" in doc:
        for scrape_results in doc["fulltext_url_dicts"]:
            if doc["oa"] == 1:
                my_webpage = WebpageInOpenRepo(url=scrape_results.get("pdf_landing_page", None))
            else:
                my_webpage = WebpageInUnknownRepo(url=scrape_results.get("pdf_landing_page", None))
            my_webpage.scraped_pdf_url = scrape_results.get("free_pdf_url", None)
            my_webpage.scraped_open_metadata_url = scrape_results.get("pdf_landing_page", None)
            my_webpage.scraped_license = license
            my_webpage.base_doc = doc
            response.append(my_webpage)

    # eventually these will have fulltext_url_dicts populated as well
    if not response:
        for url in get_urls_from_our_base_doc(doc):
            if doc["oa"] == 1:
                my_webpage = WebpageInOpenRepo(url=url)
                my_webpage.scraped_open_metadata_url = url

                # this will get handled when the oa1 urls get added
                pmcid_matches = re.findall(".*(PMC\d+).*", url)
                if pmcid_matches:
                    pmcid = pmcid_matches[0]
                    my_webpage.scraped_pdf_url = u"https://www.ncbi.nlm.nih.gov/pmc/articles/{}/pdf".format(pmcid)
            else:
                my_webpage = WebpageInClosedRepo(url=url)

            my_webpage.scraped_license = license
            my_webpage.base_doc = doc
            response.append(my_webpage)

    return response


def get_urls_from_our_base_doc(doc):
    if not doc:
        print u"no doc in get_urls_from_our_base_doc, so returning."
        return []

    response = []

    # highwire says articles are OA but they aren't.
    # example: https://www.base-search.net/Search/Results?lookfor=Democracy%2C+Elections+and+the+End+of+History&type=tit&oaboost=1&ling=1&name=&thes=&refid=dcresen&newsearch=1
    untrustworthy_base_collections = ["fthighwire"]
    for base_collection in untrustworthy_base_collections:
        if doc["id"].startswith(base_collection):
            # print u"not using the base response from {} because in untrustworthy_base_collections".format(base_collection)
            return response

    if "urls" in doc:
        # pmc can only add pmc urls.  otherwise has junk about dois that aren't actually open.
        if "sources" in doc and doc["sources"] and u"PubMed Central (PMC)" in doc["sources"]:
            for url in doc["urls"]:
                if "/pmc/" in url and url != "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
                    response += [url]
        else:
            response += doc["urls"]

    # oxford IR doesn't return URLS, instead it returns IDs from which we can build URLs
    # example: https://www.base-search.net/Record/5c1cf4038958134de9700b6144ae6ff9e78df91d3f8bbf7902cb3066512f6443/
    if "sources" in doc and doc["sources"] and "Oxford University Research Archive (ORA)" in doc["sources"]:
        if "relations" in doc and doc["relations"]:
            for relation in doc["relations"]:
                if relation.startswith("uuid"):
                    response += [u"https://ora.ox.ac.uk/objects/{}".format(relation)]

    # filter out some urls that BASE data says are open but are actually closed
    blacklist_url_snippets = [
        # these are base1s but are actually closed.  examples:  https://www.base-search.net/Search/Results?lookfor=+http%3A%2F%2Fdx.doi.org%2F10.1093%2Fanalys&type=all&oaboost=1&ling=1&name=&thes=&refid=dcresen&newsearch=1
        u"/10.1093/analys/",
        u"academic.oup.com/analysis",
        u"analysis.oxfordjournals.org/",
        u"ncbi.nlm.nih.gov/pubmed/",
        u"gateway.webofknowledge.com/"
    ]
    for url_snippet in blacklist_url_snippets:
        response = [url for url in response if url_snippet not in url]


    # filter out all the urls that go straight to publisher pages from base response
    # filter out doi urls unless they are the only url
    if len(response) > 1:
        response = [url for url in response if u"doi.org/" not in url]



    # and then html unescape them, because some are html escaped
    h = HTMLParser()
    response = [h.unescape(url) for url in response]

    return response



def normalize_title_for_querying(title):
    if not title:
        return ""
    title_to_query = ""
    title = title.lower()
    # can't just replace all punctuation because ' replaced with ? gets no hits
    title = title.replace('"', "?")
    title = title.replace('#', "?")
    title = title.replace('=', "?")
    title = title.replace('&', "?")
    title = title.replace('%', "?")
    title = title.replace('/', "?")
    title = title.replace('!', "?")
    # title = title.replace('-', "*")

    # only bother looking up titles that are at least 3 words long
    title_words = title.split()
    if len(title_words) >= 2:
        # only look up the first 12 words
        title_to_query = u" ".join(title_words[0:12])

    return title_to_query


def title_good_for_querying(title):
    if title and len(title) >= 15:
        return True
    return False

def get_open_locations_from_doc(doc, my_pub, match_type):
    open_locations = []

    try:
        urls_for_this_hit = get_urls_from_our_base_doc(doc)
        if DEBUG_BASE:
            print u"urls_for_this_hit: {}".format(urls_for_this_hit)

        if not urls_for_this_hit:
            return open_locations

        for my_webpage in get_fulltext_webpages_from_our_base_doc(doc):
            if my_webpage.is_open:
                my_webpage.related_pub = my_pub
                my_webpage.base_id = doc["id"]
                my_webpage.match_type = match_type
                my_open_version = my_webpage.mint_open_version()
                open_locations.append(my_open_version)
            else:
                if my_webpage.url not in my_pub.closed_urls:
                    my_pub.closed_urls += [my_webpage.url]
                if doc["id"] not in my_pub.closed_base_ids:
                    my_pub.closed_base_ids += [doc["id"]]

    except ValueError:  # includes simplejson.decoder.JSONDecodeError
        print u'decoding JSON has failed base response'
        pass
    except AttributeError:  # no json
        # print u"no hit with title {}".format(doc["dctitle"])
        # print u"normalized: {}".format(normalize(doc["dctitle"]))
        pass

    return open_locations


def call_our_base(my_pub, rescrape_base=False):
    start_time = time()

    if not my_pub:
        return

    for base_obj in my_pub.base_doi_links:
        if RESCRAPE_IN_CALL or rescrape_base:
            base_obj.find_fulltext()
        doc = base_obj.body["_source"]
        match_type = "doi"
        my_pub.open_locations += get_open_locations_from_doc(doc, my_pub, match_type)

    if my_pub.normalized_titles:
        crossref_title_hit = my_pub.normalized_titles[0]
        for base_title_obj in crossref_title_hit.matching_base_title_views:
            if RESCRAPE_IN_CALL or rescrape_base:
                from publication import Base
                base_obj = db.session.query(Base).get(base_title_obj.id)
                base_obj.find_fulltext()
                base_title_obj = base_obj
            match_type = None
            doc = base_title_obj.body["_source"]
            if my_pub.first_author_lastname:
                if doc.get("authors", None):
                    try:
                        base_doc_author_string = u", ".join(doc["authors"])
                        if normalize(my_pub.first_author_lastname) not in normalize(base_doc_author_string):
                            # print u"author check fails ({} not in {}), so skipping this record".format(
                            #     normalize(my_pub.first_author_lastname) , normalize(base_doc_author_string))
                            continue
                        match_type = "title and first author"
                    except TypeError:
                        pass # couldn't make author string
            if not match_type:
                match_type = "title"
            my_pub.open_locations += get_open_locations_from_doc(doc, my_pub, match_type)

    # print u"finished base step of set_fulltext_urls with in {}s".format(
    #     elapsed(start_time, 2))



# titles_string = remove_punctuation("Authors from the periphery countries choose open access more often (preprint)")
# url_template = u"https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi?func=PerformSearch&query=dctitle:({titles_string})&format=json"
# url = url_template.format(titles_string=titles_string)
# print u"calling base with {}".format(url)
#
# proxy_url = os.getenv("STATIC_IP_PROXY")
# proxies = {"https": proxy_url}
# r = requests.get(url, proxies=proxies, timeout=6)
# r.json()
# id_string = "{}{}".format(dccollection, dcdoi)