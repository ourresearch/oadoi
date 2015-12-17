import requests
from StringIO import StringIO
from util import ordinal
"""
Code shared among Person, Package, and Tag
"""


def make_badge_io(entity):
    percentile_int = int(round(entity.impact_percentile * 100))
    percentile_str = ordinal(percentile_int)
    color = "brightgreen"

    url_template = "http://img.shields.io/badge/Depsy-{percentile}%20percentile-{color}.svg?style=flat"
    url = url_template.format(
        percentile=percentile_str,
        color=color
    )

    print "sending request for badge to this URL: ", url
    try:
        ret = requests.get(url).content
    except requests.exceptions.SSLError:
        # fake response to handle fact that SSL on OSX breaks for shields.io
        ret = '<svg xmlns="http://www.w3.org/2000/svg" width="260" height="20"><linearGradient id="b" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><mask id="a"><rect width="260" height="20" rx="3" fill="#fff"/></mask><g mask="url(#a)"><path fill="#555" d="M0 0h158v20H0z"/><path fill="#4c1" d="M158 0h102v20H158z"/><path fill="url(#b)" d="M0 0h260v20H0z"/></g><g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="79" y="15" fill="#010101" fill-opacity=".3">Research software impact</text><text x="79" y="14">Research software impact</text><text x="208" y="15" fill="#010101" fill-opacity=".3">42nd percentile</text><text x="208" y="14">42nd percentile</text></g></svg>'


    return StringIO(ret)


