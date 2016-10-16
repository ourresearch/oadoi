import os
import requests
from time import time
from collections import defaultdict

import oa_local
from util import elapsed
from util import normalize
from util import pick_best_url

def call_base(products):
    if not products:
        print "empty product list so not calling base"
        return

    titles = []
    # may be more than one product for a given title, so is a dict of lists
    titles_to_products = defaultdict(list)

    for p in products:
        title = p.title
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
    url_template = u"https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi?func=PerformSearch&query=(dcoa:1%20OR%20dcoa:2)%20AND%20dctitle:({titles_string})&fields=dctitle,dccreator,dcyear,dcrights,dcprovider,dcidentifier,dcoa,dclink&hits=100000&format=json"
    url = url_template.format(titles_string=titles_string)
    # print u"{}: calling base with {}".format(self.id, url)

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
                    matching_products = titles_to_products[normalize(doc["dctitle"])]
                    for p in matching_products:
                        if base_dcoa == "1":
                            # got a 1 hit.  yay!  overwrite no matter what.
                            p.fulltext_url = pick_best_url(doc["dcidentifier"])
                            p.open_step = "base 1"
                            p.repo_urls["urls"] = {}
                            p.base_dcoa = base_dcoa
                            p.base_dcprovider = doc["dcprovider"]
                            if not p.license_string:
                                p.license_string = ""
                            p.license_string += u"{};".format(doc["dcrights"])
                        elif base_dcoa == "2" and p.base_dcoa != "1":
                            # got a 2 hit.  use only if we don't already have a 1.
                            p.repo_urls["urls"] += doc["dcidentifier"]
                            p.base_dcoa = base_dcoa
                            p.base_dcprovider = doc["dcprovider"]
                except KeyError:
                    # print u"no hit with title {}".format(doc["dctitle"])
                    # print u"normalized: {}".format(normalize(doc["dctitle"]))
                    pass
        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            print u'decoding JSON has failed base response'
            for p in products:
                p.base_dcoa = u"base lookup error: json response parsing"
        except AttributeError:  # no json
            # print u"no hit with title {}".format(doc["dctitle"])
            # print u"normalized: {}".format(normalize(doc["dctitle"]))
            pass

    for p in products:
        if p.license_string:
            p.license = oa_local.find_normalized_license(p.license_string)


    print u"finished base step of set_fulltext_urls with {} titles in {}s".format(
        len(titles_to_products), elapsed(start_time, 2))
