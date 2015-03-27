import os
import requests

url_template = "https://api.elsevier.com/content/search/index:SCOPUS?query=PMID({pmid})&field=citedby-count&apiKey={scopus_key}&insttoken={scopus_insttoken}"
scopus_insttoken = os.environ["SCOPUS_INSTTOKEN"]
scopus_key = os.environ["SCOPUS_KEY"]

def get_scopus_citations(pmid):
    response = ""
    url = url_template.format(
            scopus_insttoken=scopus_insttoken,
            scopus_key=scopus_key,
            pmid=pmid
        )

    headers = {}
    headers["accept"] = "application/json"
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        response = "bad scopus status code"

    else:
        if "Result set was empty" in r.text:
            #logger.warning(u"empty result set with doi {url}".format(url=url))
            response = "empty result set"
        else:
            try:
                data = r.json()
                response = data["search-results"]["entry"][0]["citedby-count"]
                print response
            except (KeyError, ValueError):
                # not in Scopus database
                response = "not found"
    return response