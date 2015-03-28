from app import app
from scopus import get_scopus_citations_for_pmids
from pubmed import get_pmids_from_author_name

from flask import Flask
from flask import make_response
import os
import json

def json_resp_from_thing(thing):
    json_str = json.dumps(thing, sort_keys=True, indent=4)
    resp = make_response(json_str, 200)
    resp.mimetype = "application/json"
    return resp


def abort_json(status_code, msg):
    body_dict = {
        "HTTP_status_code": status_code,
        "message": msg,
        "error": True
    }
    resp_string = json.dumps(body_dict, sort_keys=True, indent=4)
    resp = make_response(resp_string, status_code)
    resp.mimetype = "application/json"
    abort(resp)



@app.route("/")
def hello():
    return "Hello world!"


@app.route("/author/<author_name>/pmids")
def author_pmids(author_name):
    pmids = get_pmids_from_author_name(author_name)
    return json_resp_from_thing(pmids)

@app.route("/author/<author_name>/scopus")
def author_scopus(author_name):
    pmids = get_pmids_from_author_name(author_name)
    citations = get_scopus_citations_for_pmids(pmids)
    return json_resp_from_thing(citations)

@app.route("/pmids/<pmids_string>/scopus")
def pmids_scopus(pmids_string):
    pmids = pmids_string.split(",")
    response = get_scopus_citations_for_pmids(pmids)
    return json_resp_from_thing(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5008))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
