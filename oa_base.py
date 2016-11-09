import os
import requests
from time import time
from Levenshtein import ratio
from collections import defaultdict

from webpage import PublisherWebpage, WebpageInOpenRepo, WebpageInUnknownRepo
from util import elapsed
from util import normalize





def get_urls_from_our_base_doc(doc):
    response = []

    if "urls" in doc:
        # pmc can only add pmc urls.  otherwise has junk about dois that aren't actually open.
        if "PubMed Central (PMC)" in doc["sources"]:
            for url in doc["urls"]:
                if "/pmc/" in url and url != "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
                    response += [url]
        else:
            response += doc["urls"]

    # oxford IR doesn't return URLS, instead it returns IDs from which we can build URLs
    # example: https://www.base-search.net/Record/5c1cf4038958134de9700b6144ae6ff9e78df91d3f8bbf7902cb3066512f6443/
    if "sources" in doc and "Oxford University Research Archive (ORA)" in doc["sources"]:
        if "relations" in doc:
            for relation in doc["relations"]:
                if relation.startswith("uuid"):
                    response += [u"https://ora.ox.ac.uk/objects/{}".format(relation)]

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
    # title = title.replace('-', "*")

    # only bother looking up titles that are at least 3 words long
    title_words = title.split()
    if len(title_words) >= 3:
        # only look up the first 12 words
        title_to_query = u" ".join(title_words[0:12])

    return title_to_query



def call_our_base(my_pub):
    if not my_pub:
        return

    webpages_to_return = []
    found_a_base1 = False
    title = my_pub.best_title
    title_to_query = normalize_title_for_querying(title)

    if not title_to_query:
        return webpages_to_return

    # now do the lookup in base
    # query_string = u'title=%22{}%22'.format(title_to_query)
    query_string = u'title:({})'.format(title_to_query)

    if my_pub.first_author_lastname:
        query_string += u" AND authors:({})".format(my_pub.first_author_lastname)

    # if my_product.doi:
    #     query_string += u" OR urls={}".format(my_product.doi)

    # print u"{}: calling base with query string of length {}, utf8 bits {}".format(self.id, len(titles_string), 8*len(titles_string.encode('utf-8')))
    url_template = u"{base_url}/base/_search?pretty&size=20&q={query_string}"
    url = url_template.format(base_url=os.getenv("BASE_URL"), query_string=query_string)

    # print u"calling our base with {}\n".format(url)

    start_time = time()
    r = None
    try:
        r = requests.get(url, timeout=10)
        # print u"** querying with {} titles took {}s".format(len(titles), elapsed(start_time))
    except requests.exceptions.ConnectionError:
        print u"connection error in call_our_base, skipping."
    except requests.Timeout:
        print u"TIMEOUT error in call_our_base, skipping."

    if r != None and r.status_code != 200:
        print u"problem searching base! status_code={}".format(r.status_code)
        my_pub.base_dcoa = u"base query error: status_code={}".format(r.status_code)

    else:
        try:
            data = r.json()["hits"]["hits"]

            # print "number found:", data["numFound"]

            for hit in data:
                doc = hit["_source"]

                title_matches = False
                normalized_pub_title = normalize(my_pub.best_title)
                normalized_base_title = normalize(doc["title"])
                lev_ratio = ratio(normalized_pub_title, normalized_base_title)

                if len(my_pub.best_title) < 40 or len(doc["title"]) < 40:
                    if normalized_pub_title==normalized_base_title:
                        title_matches = True
                else:
                    if normalized_pub_title in normalized_base_title:
                        title_matches = True
                    if normalized_base_title in normalized_pub_title:
                        title_matches = True
                    # only fuzzy match if we don't have exact matches

                # if doing a fuzzy match, make sure the query included a last name
                if not title_matches:
                    # print u"{}\n{}\n{}\n{}".format(lev_ratio, normalized_pub_title, normalized_base_title, get_urls_from_our_base_doc(doc))
                    if my_pub.first_author_lastname:
                        if lev_ratio > 0.8:
                            title_matches = True
                    else:
                        if lev_ratio > 0.95:
                            title_matches = True


                if title_matches:
                    if doc["oa"] == 1:
                        found_a_base1 = True
                        for url in get_urls_from_our_base_doc(doc):
                            my_webpage = WebpageInOpenRepo(url=url, related_pub=my_pub)
                            if "rights" in doc:
                                my_webpage.scraped_license = oa_local.find_normalized_license(format(doc["rights"]))
                            webpages_to_return.append(my_webpage)

                    elif doc["oa"] == 2 and not found_a_base1:
                        for url in get_urls_from_our_base_doc(doc):
                            my_webpage = WebpageInUnknownRepo(url=url, related_pub=my_pub)
                            webpages_to_return.append(my_webpage)

        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            print u'decoding JSON has failed base response'
            my_pub.base_dcoa = u"base lookup error: json response parsing"
        except AttributeError:  # no json
            # print u"no hit with title {}".format(doc["dctitle"])
            # print u"normalized: {}".format(normalize(doc["dctitle"]))
            pass

    print u"finished base step of set_fulltext_urls with in {}s".format(
        elapsed(start_time, 2))

    # print u"found these webpages in base: {}".format(webpages_to_return)
    return webpages_to_return



