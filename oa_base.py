import os
import requests
from time import time
from collections import defaultdict

import oa_local
from util import elapsed
from util import normalize

def base_url_sort_score(url):
    # sometimes base returns just this.  don't use this url.
    if url=="http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
        return 10

    if "citeseerx" in url:
        return 5

    # sometimes the base doi isn't actually open, like in this record:
    # https://www.base-search.net/Record/9b574f9768c8c25d9ed6dd796191df38a865f870fde492ee49138c6100e31301/
    # so sort doi down in the list
    if "doi.org" in url:
        return 1

    # pubmed results not as good as pmc results
    if "/pubmed/" in url:
        return 0

    # arxiv results are better than IR results, if we've got them
    if "arxiv" in url:
        return -2

    # pmc results are better than IR results, if we've got them
    if "/pmc/" in url:
        return -3

    if ".edu" in url:
        return -9

    # otherwise whatever we've got
    return -10


def pick_best_base_url(urls):
    return sorted(urls, key=lambda x:base_url_sort_score(x))[0]


# base has some records where there are multiple titles
# in the future, fix these by checking the first authors match
# for now just do overrides
BASE_RESULT_OVERRIDE = {
    normalize("Cluster-state quantum computation"): "http://arxiv.org/abs/quant-ph/0504097"
}

def get_urls_from_base_doc(doc):
    response = []

    if "dcidentifier" in doc:
        response += doc["dcidentifier"]

    # oxford IR doesn't return URLS, instead it returns IDs from which we can build URLs
    # example: https://www.base-search.net/Record/5c1cf4038958134de9700b6144ae6ff9e78df91d3f8bbf7902cb3066512f6443/
    if "dcprovider" in doc and doc["dcprovider"]=="Oxford University Research Archive (ORA)":
        if "dcrelation" in doc:
            for relation in doc["dcrelation"]:
                if relation.startswith("uuid"):
                    response += [u"https://ora.ox.ac.uk/objects/{}".format(relation)]

    return response


def get_urls_from_our_base_doc(doc):
    response = []

    if "urls" in doc:
        response += doc["urls"]

    # oxford IR doesn't return URLS, instead it returns IDs from which we can build URLs
    # example: https://www.base-search.net/Record/5c1cf4038958134de9700b6144ae6ff9e78df91d3f8bbf7902cb3066512f6443/
    if "sources" in doc and "Oxford University Research Archive (ORA)" in doc["sources"]:
        if "relations" in doc:
            for relation in doc["relations"]:
                if relation.startswith("uuid"):
                    response += [u"https://ora.ox.ac.uk/objects/{}".format(relation)]

    return response

def call_base(products):
    if not products:
        # print "empty product list so not calling base"
        return

    titles = []
    # may be more than one product for a given title, so is a dict of lists
    titles_to_products = defaultdict(list)

    for p in products:
        p.license_string = ""
        p.base_dcoa = None
        p.repo_urls = {"urls": []}

        title = p.best_title
        if title:
            titles_to_products[normalize(title)].append(p)

            title = title.lower()
            # can't just replace all punctuation because ' replaced with ? gets no hits
            title = title.replace('"', "?")
            title = title.replace('#', "?")
            title = title.replace('=', "?")
            title = title.replace('&', "?")
            title = title.replace('%', "?")
            title = title.replace('-', "*")

            # only bother looking up titles that are at least 3 words long
            title_words = title.split()
            if len(title_words) >= 3:
                # only look up the first 12 words
                title_to_query = u" ".join(title_words[0:12])
                titles.append(title_to_query)

    # now do the lookup in base
    titles_string = u"%20OR%20".join([u'%22{}%22'.format(title) for title in titles])
    # print u"{}: calling base with query string of length {}, utf8 bits {}".format(self.id, len(titles_string), 8*len(titles_string.encode('utf-8')))
    url_template = u"https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi?func=PerformSearch&query=(dcoa:1%20OR%20dcoa:2)%20AND%20dctitle:({titles_string})&fields=dctitle,dccreator,dcyear,dcrights,dcrelation,dcprovider,dcidentifier,dcoa,dclink&hits=100000&format=json"
    url = url_template.format(titles_string=titles_string)

    # print u"calling base with {}".format(url)

    start_time = time()
    proxy_url = os.getenv("STATIC_IP_PROXY")
    proxies = {"https": proxy_url}
    r = None
    try:
        r = requests.get(url, proxies=proxies, timeout=6)
        # print u"** querying with {} titles took {}s".format(len(titles), elapsed(start_time))
    except requests.exceptions.ConnectionError:
        print u"connection error in set_fulltext_urls, skipping."
    except requests.Timeout:
        print u"timeout error in set_fulltext_urls, skipping."

    if r != None and r.status_code != 200:
        print u"problem searching base! status_code={}".format(r.status_code)
        for p in products:
            p.base_dcoa = u"base query error: status_code={}".format(r.status_code)

    else:
        try:
            data = r.json()["response"]

            # print "number found:", data["numFound"]
            for doc in data["docs"]:
                base_dcoa = str(doc["dcoa"])
                try:
                    # print "normalize(doc['dctitle'])", normalize(doc["dctitle"]), doc["dctitle"], doc["dcidentifier"]
                    # print "titles", titles
                    matching_products = titles_to_products[normalize(doc["dctitle"])]
                except KeyError:
                    matching_products = []
                for p in matching_products:
                    if base_dcoa == "1":
                        # got a 1 hit.  yay!  overwrite no matter what.
                        urls_to_choose_from = get_urls_from_base_doc(doc)
                        if p.fulltext_url:
                            urls_to_choose_from += [p.fulltext_url]
                        p.fulltext_url = pick_best_base_url(urls_to_choose_from)
                        p.repo_urls["urls"] = {}
                        p.evidence = "oa repository (via base-search.net oa url)"
                        p.base_dcoa = base_dcoa
                        if "dcrights" in doc:
                            p.license_string += u"{};".format(doc["dcrights"])

                    elif base_dcoa == "2" and p.base_dcoa != "1":
                        # got a 2 hit.  use only if we don't already have a 1.
                        p.repo_urls["urls"] += get_urls_from_base_doc(doc)
                        p.base_dcoa = base_dcoa

        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            print u'decoding JSON has failed base response'
            for p in products:
                p.base_dcoa = u"base lookup error: json response parsing"
        except AttributeError:  # no json
            # print u"no hit with title {}".format(doc["dctitle"])
            # print u"normalized: {}".format(normalize(doc["dctitle"]))
            pass

    if p.repo_urls["urls"]:
        p.repo_urls["urls"] = sorted(p.repo_urls["urls"], key=lambda x:base_url_sort_score(x))

    for p in products:
        if p.license_string:
            p.license = oa_local.find_normalized_license(p.license_string)
        if p.best_title and (normalize(p.best_title) in BASE_RESULT_OVERRIDE):
            p.fulltext_url = BASE_RESULT_OVERRIDE[normalize(p.best_title)]

    print u"finished base step of set_fulltext_urls with {} titles in {}s".format(
        len(titles_to_products), elapsed(start_time, 2))


def call_our_base(my_product):
    if not my_product:
        # print "empty product list so not calling base"
        return

    titles = []
    # may be more than one product for a given title, so is a dict of lists
    titles_to_products = defaultdict(list)

    my_product.license_string = ""
    my_product.base_dcoa = None
    my_product.repo_urls = {"urls": []}

    title = my_product.best_title
    title_to_query = ""
    if title:
        title = title.lower()
        # can't just replace all punctuation because ' replaced with ? gets no hits
        title = title.replace('"', "?")
        title = title.replace('#', "?")
        title = title.replace('=', "?")
        title = title.replace('&', "?")
        title = title.replace('%', "?")
        title = title.replace('-', "*")

        # only bother looking up titles that are at least 3 words long
        title_words = title.split()
        if len(title_words) >= 3:
            # only look up the first 12 words
            title_to_query = u" ".join(title_words[0:12])

    # now do the lookup in base
    if not title_to_query:
        return

    query_string = u'title=%22{}%22'.format(title_to_query)
    if my_product.doi:
        query_string += u" OR urls={}".format(my_product.doi.replace("/", "\/"))

    # print u"{}: calling base with query string of length {}, utf8 bits {}".format(self.id, len(titles_string), 8*len(titles_string.encode('utf-8')))
    url_template = u"{base_url}/base/_search?pretty&size=20&q={query_string}"
    url = url_template.format(base_url=os.getenv("BASE_URL"), query_string=query_string)

    print u"calling our base with {}".format(url)

    start_time = time()
    r = None
    try:
        r = requests.get(url, timeout=6)
        # print u"** querying with {} titles took {}s".format(len(titles), elapsed(start_time))
    except requests.exceptions.ConnectionError:
        print u"connection error in set_fulltext_urls, skipping."
    except requests.Timeout:
        print u"timeout error in set_fulltext_urls, skipping."

    if r != None and r.status_code != 200:
        print u"problem searching base! status_code={}".format(r.status_code)
        my_product.base_dcoa = u"base query error: status_code={}".format(r.status_code)

    else:
        try:
            data = r.json()["hits"]["hits"]

            # print "number found:", data["numFound"]
            for hit in data:
                doc = hit["_source"]
                if not normalize(my_product.best_title) == normalize(doc["title"]):
                    continue

                base_dcoa = str(doc["oa"])
                if base_dcoa == "1":
                    # got a 1 hit.  yay!  overwrite no matter what.
                    urls_to_choose_from = get_urls_from_our_base_doc(doc)
                    if my_product.fulltext_url:
                        urls_to_choose_from += [my_product.fulltext_url]
                    my_product.fulltext_url = pick_best_base_url(urls_to_choose_from)
                    my_product.repo_urls["urls"] = {}
                    my_product.evidence = "oa repository (via base-search.net oa url)"
                    my_product.base_dcoa = base_dcoa
                    if "rights" in doc:
                        my_product.license_string += u"{};".format(doc["rights"])

                elif base_dcoa == "2" and my_product.base_dcoa != "1":
                    # got a 2 hit.  use only if we don't already have a 1.
                    my_product.repo_urls["urls"] += get_urls_from_our_base_doc(doc)
                    my_product.base_dcoa = base_dcoa

        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            print u'decoding JSON has failed base response'
            my_product.base_dcoa = u"base lookup error: json response parsing"
        except AttributeError:  # no json
            # print u"no hit with title {}".format(doc["dctitle"])
            # print u"normalized: {}".format(normalize(doc["dctitle"]))
            pass

    if my_product.repo_urls["urls"]:
        my_product.repo_urls["urls"] = sorted(my_product.repo_urls["urls"], key=lambda x:base_url_sort_score(x))

    if my_product.license_string:
        my_product.license = oa_local.find_normalized_license(my_product.license_string)
    if my_product.best_title and (normalize(my_product.best_title) in BASE_RESULT_OVERRIDE):
        my_product.fulltext_url = BASE_RESULT_OVERRIDE[normalize(my_product.best_title)]

    print u"finished base step of set_fulltext_urls with in {}s".format(
        elapsed(start_time, 2))
