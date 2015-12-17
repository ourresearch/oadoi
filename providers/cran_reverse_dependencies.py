import requests
import os
from lxml import html

import logging
logger = logging.getLogger("cran_reverse_dependencies")

url_template = "https://cran.r-project.org/web/packages/%s/"


def get_data(reponame):
    data_url = url_template % reponame
    print data_url
    response = requests.get(data_url)
    if "Reverse" in response.text:
        page = response.text
        page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
        tree = html.fromstring(page)
        data = {}
        data["reverse_imports"] = tree.xpath('//tr[(starts-with(td[1], "Reverse imports"))]/td[2]/a/text()')
        data["reverse_depends"] = tree.xpath('//tr[(starts-with(td[1], "Reverse depends"))]/td[2]/a/text()')
        data["reverse_suggests"] = tree.xpath('//tr[(starts-with(td[1], "Reverse suggests"))]/td[2]/a/text()')
        data["reverse_enhances"] = tree.xpath('//tr[(starts-with(td[1], "Reverse enhances"))]/td[2]/a/text()')
        used_by_set = set(data["reverse_imports"] + data["reverse_depends"] + data["reverse_suggests"] + data["reverse_enhances"])
        data["used_by"] = list(used_by_set)
        data["used_by_count"] = len(used_by_set)

    else:
        data = None
    return data
