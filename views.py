from app import app
from scopus import get_scopus_citations
from pubmed import get_pmids_from_author_name

from flask import Flask
import os
import json

@app.route("/")
def hello():
    return "Hello world!"


@app.route("/author/<author_name>/pmids")
def author_pmids(author_name):
    result = get_pmids_from_author_name(author_name)
    return json.dumps(result, indent=4)


@app.route("/pmids/<pmids_string>/scopus")
def scopus(pmids_string):
    pmids = pmids_string.split(",")
    response = {}
    for pmid in pmids:
        response[pmid] = get_scopus_citations(pmid)

    return json.dumps(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5008))
    app.run(host='0.0.0.0', port=port)
