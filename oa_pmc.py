#!/usr/bin/python
# -*- coding: utf-8 -*-

from cachetools import LRUCache
from kids.cache import cache

from http_cache import http_get


# examples
# https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMC3039489&resulttype=core&format=json&tool=oadoi
# https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMC3606428&resulttype=core&format=json&tool=oadoi
# https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=10.1093/jisesa/iex068&resulttype=core&format=json&tool=oadoi


@cache(use=LRUCache(maxsize=32))
def query_pmc(query_text):
    if not query_text:
        return None

    url_template = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={}&resulttype=core&format=json&tool=oadoi"
    url = url_template.format(query_text)

    r = http_get(url)
    data = r.json()
    result_list = data["resultList"]["result"]
    return result_list
