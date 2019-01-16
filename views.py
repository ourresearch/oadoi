from flask import make_response
from flask import request
from flask import redirect
from flask import abort
from flask import render_template
from flask import jsonify
from flask import g
from flask import url_for
from flask import Response

import json
import os
import sys
import requests
from time import time
from time import sleep
from datetime import datetime
import unicodecsv
from io import BytesIO
from collections import defaultdict

from app import app
from app import db
from app import logger

import pub
import repository
from accuracy_report import AccuracyReport
from emailer import create_email
from emailer import send
from search import fulltext_search_title
from search import autocomplete_phrases
from changefile import get_changefile_dicts
from changefile import valid_changefile_api_keys
from changefile import get_file_from_bucket
from util import NoDoiException
from util import safe_commit
from util import elapsed
from util import clean_doi
from util import restart_dynos
from util import get_sql_answers



def json_dumper(obj):
    """
    if the obj has a to_dict() function we've implemented, uses it to get dict.
    from http://stackoverflow.com/a/28174796
    """
    try:
        return obj.to_dict()
    except AttributeError:
        return obj.__dict__


def json_resp(thing):
    json_str = json.dumps(thing, sort_keys=True, default=json_dumper, indent=4)

    if request.path.endswith(".json") and (os.getenv("FLASK_DEBUG", False) == "True"):
        logger.info(u"rendering output through debug_api.html template")
        resp = make_response(render_template(
            'debug_api.html',
            data=json_str))
        resp.mimetype = "text/html"
    else:
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


def log_request(resp):
    log_dict = {}
    if resp.status_code == 200:
        if request.endpoint == "get_doi_endpoint":
            try:
                results = json.loads(resp.get_data())["results"][0]
            except Exception:
                # don't bother logging if no results
                return
            oa_color = results["oa_color"]
            if not oa_color:
                oa_color = "gray"
            if oa_color == "green":
                host_type = "repository"
            elif oa_color == "gray":
                host_type = None
            else:
                host_type = "publisher"

            log_dict = {
                "doi": results["doi"],
                "email": request.args.get("email", "no_email_given"),
                "year": results.get("year", None),
                "publisher": None,
                "is_oa": oa_color != "gray",
                "host_type": host_type,
                "license": results.get("license", None),
                "journal_is_oa": None
            }
        elif request.endpoint == "get_doi_endpoint_v2":
            try:
                results = json.loads(resp.get_data())
                best_oa_location = results.get("best_oa_location", None)
            except Exception:
                # don't bother logging if no results
                return
            host_type = None
            license = None
            if best_oa_location:
                host_type = best_oa_location.get("host_type", None)
                license = best_oa_location.get("license", None)
            log_dict = {
                "doi": results["doi"],
                "email": request.args.get("email", "no_email_given"),
                "year": results.get("year", None),
                "publisher": results.get("publisher", None),
                "is_oa": results.get("is_oa", None),
                "host_type": host_type,
                "license": license,
                "journal_is_oa": results.get("journal_is_oa", None)
            }

    if log_dict:
        logger.info(u"logthis: {}".format(json.dumps(log_dict)))


@app.after_request
def after_request_stuff(resp):

    #support CORS
    resp.headers['Access-Control-Allow-Origin'] = "*"
    resp.headers['Access-Control-Allow-Methods'] = "POST, GET, OPTIONS, PUT, DELETE, PATCH"
    resp.headers['Access-Control-Allow-Headers'] = "origin, content-type, accept, x-requested-with"

    # remove session
    db.session.remove()

    # without this jason's heroku local buffers forever
    sys.stdout.flush()

    # log request for analytics
    log_request(resp)

    return resp



@app.before_request
def stuff_before_request():
    if request.endpoint in ["get_doi_endpoint_v2", "get_doi_endpoint"]:
        email = request.args.get("email", None)
        if not email or email.endswith(u"example.com"):
            abort_json(422, "Email address required in API call, see http://unpaywall.org/products/api")

    if get_ip() in ["35.200.160.130", "45.249.247.101", "137.120.7.33",
                    "52.56.108.147", "193.137.134.252", "130.225.74.231"]:
        abort_json(429, "History of API use exceeding rate limits, please email team@impactstory.org for other data access options, including free full database dump.")

    g.request_start_time = time()
    g.hybrid = False
    if 'hybrid' in request.args.keys():
        g.hybrid = True
        logger.info(u"GOT HYBRID PARAM so will run with hybrid.")

    # don't redirect http api in some cases
    if request.url.startswith("http://api."):
        return
    if "staging" in request.url or "localhost" in request.url:
        return

    # redirect everything else to https.
    new_url = None
    try:
        if request.headers["X-Forwarded-Proto"] == "https":
            pass
        elif "http://" in request.url:
            new_url = request.url.replace("http://", "https://")
    except KeyError:
        # logger.info(u"There's no X-Forwarded-Proto header; assuming localhost, serving http.")
        pass

    # redirect to naked domain from www
    if request.url.startswith("https://www.oadoi.org"):
        new_url = request.url.replace(
            "https://www.oadoi.org",
            "https://oadoi.org"
        )
        logger.info(u"URL starts with www; redirecting to " + new_url)

    if new_url:
        return redirect(new_url, 301)  # permanent



# convenience function because we do this in multiple places
def get_multiple_pubs_response():
    is_person_who_is_making_too_many_requests = False

    biblios = []
    body = request.json
    if "dois" in body:
        if len(body["dois"]) > 25:
            abort_json(413, "max number of DOIs is 25")
        if len(body["dois"]) > 1:
            is_person_who_is_making_too_many_requests = True
        for doi in body["dois"]:
            biblios += [{"doi": doi}]
            if u"jama" in doi:
                is_person_who_is_making_too_many_requests = True

    elif "biblios" in body:
        for biblio in body["biblios"]:
            biblios += [biblio]

        if len(body["biblios"]) > 1:
            is_person_who_is_making_too_many_requests = True

    logger.info(u"in get_multiple_pubs_response with {}".format(biblios))


    run_with_hybrid = g.hybrid
    if is_person_who_is_making_too_many_requests:
        logger.info(u"is_person_who_is_making_too_many_requests, so returning 429")
        abort_json(429, u"sorry, you are calling us too quickly.  Please email team@impactstory.org so we can figure out a good way to get you the data you are looking for.")
    pubs = pub.get_pubs_from_biblio(biblios, run_with_hybrid)
    return pubs


def get_pub_from_doi(doi):
    run_with_hybrid = g.hybrid
    skip_all_hybrid = "skip_all_hybrid" in request.args
    try:
        my_pub = pub.get_pub_from_biblio({"doi": doi},
                                         run_with_hybrid=run_with_hybrid,
                                         skip_all_hybrid=skip_all_hybrid
                                         )
    except NoDoiException:
        abort_json(404, u"'{}' is an invalid doi.  See http://doi.org/{}".format(doi, doi))
    return my_pub

@app.route("/data/repo_pulse/test/<path:url>", methods=["GET"])
def repo_pulse_test_url(url):
    from repository import test_harvest_url
    results = test_harvest_url(url)
    return jsonify({"results": results})


@app.route("/data/repo_pulse/<path:query_string>", methods=["GET"])
def repo_pulse_get_endpoint(query_string):
    query_parts = query_string.split(",")
    objs = []
    for query_part in query_parts:
        objs += repository.lookup_repo_by_pmh_url(query_part)
    return jsonify({"results": [obj.to_dict() for obj in objs]})

@app.route("/debug/repo/search/<path:query_string>", methods=["GET"])
def debug_repo_endpoint_search(query_string):
    repos = repository.get_raw_repo_meta(query_string)
    endpoints = []
    for repo in repos:
        for endpoint in repo.endpoints:
            endpoints.append(endpoint)
    return jsonify({"results": [obj.to_dict() for obj in endpoints]})


def get_endpoints_from_query_string(query_string):
    if "," in query_string:
        repo_ids = query_string.split(",")
    else:
        repo_ids = [query_string]
    repos = repository.get_repos_by_ids(repo_ids)
    endpoints = []
    for repo in repos:
        for endpoint in repo.endpoints:
            endpoints.append(endpoint)
    return endpoints

@app.route("/debug/repo/<query_string>", methods=["GET"])
def debug_repo_endpoint(query_string):
    endpoints = get_endpoints_from_query_string(query_string)
    return jsonify({"results": [obj.to_dict() for obj in endpoints]})

@app.route("/debug/repo/<query_string>/examples/closed", methods=["GET"])
def debug_repo_examples_closed(query_string):
    endpoints = get_endpoints_from_query_string(query_string)
    return jsonify({"results": [obj.get_closed_pages() for obj in endpoints]})

@app.route("/debug/repo/<query_string>/examples/open", methods=["GET"])
def debug_repo_examples_open(query_string):
    endpoints = get_endpoints_from_query_string(query_string)
    return jsonify({"results": [obj.get_open_pages() for obj in endpoints]})


@app.route("/data/sources/<query_string>", methods=["GET"])
def sources_endpoint_search(query_string):
    objs = repository.get_sources_data(query_string)
    return jsonify({"results": [obj.to_dict() for obj in objs]})

@app.route("/data/sources.csv", methods=["GET"])
def sources_endpoint_csv():
    objs = repository.get_sources_data()
    data_string = u"\n".join([obj.to_csv_row() for obj in objs])
    data_string = unicode(data_string).encode("utf-8")
    output = make_response(data_string)
    output.headers["Content-Disposition"] = "attachment; filename=unpaywall_sources.csv"
    output.headers["Content-type"] = "text/csv; charset=UTF-8"
    return output


@app.route("/data/sources", methods=["GET"])
def sources_endpoint():
    sources = repository.get_sources_data_fast()
    return jsonify({"results": [s.to_dict() for s in sources]})


@app.route("/data/repositories", methods=["GET"])
def repositories_endpoint():
    repository_metadata_objects = repository.get_repository_data()
    return jsonify({"results": [repo_meta.to_dict() for repo_meta in repository_metadata_objects]})


@app.route("/v1/publication/doi/<path:doi>", methods=["GET"])
@app.route("/v1/publication/doi.json/<path:doi>", methods=["GET"])
def get_from_new_doi_endpoint(doi):
    my_pub = get_pub_from_doi(doi)
    return jsonify({"results": [my_pub.to_dict_v1()]})



def get_ip():
    # from http://stackoverflow.com/a/12771438/596939
    if request.headers.getlist("X-Forwarded-For"):
       ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
       ip = request.remote_addr
    return ip


def print_ip():
    user_agent = request.headers.get('User-Agent')
    logger.info(u"calling from IP {ip}. User-Agent is '{user_agent}'.".format(
        ip=get_ip(),
        user_agent=user_agent
    ))


# this is the old way of expressing this endpoint.
# the new way is POST api.oadoi.org/
# you can give it an object that lists DOIs
# you can also give it an object that lists biblios.
# this is undocumented and is just for impactstory use now.
@app.route("/v1/publications", methods=["POST"])
def new_post_publications_endpoint():
    print_ip()
    pubs = get_multiple_pubs_response()
    if not pubs:
        abort_json(500, "something went wrong.  please email team@impactstory.org and we'll have a look!")
    return jsonify({"results": [p.to_dict_v1() for p in pubs]})



# this endpoint is undocumented for public use, and we don't really use it
# in production either.
# it's just for testing the POST biblio endpoint.
@app.route("/biblios", methods=["GET"])
@app.route("/biblios.json", methods=["GET"])
@app.route("/v1/publication", methods=["GET"])
@app.route("/v1/publication.json", methods=["GET"])
def get_from_biblio_endpoint():
    request_biblio = {}
    for (k, v) in request.args.iteritems():
        request_biblio[k] = v
    run_with_hybrid = g.hybrid
    my_pub = pub.get_pub_from_biblio(request_biblio, run_with_hybrid=run_with_hybrid)
    return json_resp({"results": [my_pub_v1.to_dict()]})




@app.route("/favicon.ico")
def favicon_ico():
    return redirect(url_for("static", filename="img/favicon.ico"))

@app.route("/browser-tools/bookmarklet.js")
def bookmarklet_js():
    base_url = request.url.replace(
        "browser-tools/bookmarklet.js",
        "static/browser-tools/"
    )

    if "localhost:" not in base_url:
        # seems like this shouldn't be necessary. but i think
        # flask's request.url is coming in with http even when
        # we asked for https on the server. weird.
        base_url = base_url.replace("http://", "https://")

    rendered = render_template(
        "browser-tools/bookmarklet.js",
        base_url=base_url
    )
    resp = make_response(rendered, 200)
    resp.mimetype = "application/javascript"
    return resp



@app.route('/', methods=["GET", "POST"])
def base_endpoint():
    return jsonify({
        "version": "1.3.0",
        "documentation_url": "https://unpaywall.org/data",
        "msg": "Don't panic"
    })

@app.route('/v2', methods=["GET", "POST"])
@app.route('/v2/', methods=["GET", "POST"])
def base_endpoint_v2():
    return jsonify({
        "version": "2.0.1",
        "documentation_url": "https://unpaywall.org/api/v2",
        "msg": "Don't panic"
    })

@app.route("/<path:doi>", methods=["GET"])
def get_doi_endpoint(doi):
    # the GET api endpoint (returns json data)
    my_pub = get_pub_from_doi(doi)
    return jsonify({"results": [my_pub.to_dict_v1()]})

@app.route("/v2/<path:doi>", methods=["GET"])
def get_doi_endpoint_v2(doi):
    # the GET api endpoint (returns json data)
    my_pub = get_pub_from_doi(doi)
    return jsonify(my_pub.to_dict_v2())

@app.route("/v2/dois", methods=["POST"])
def simple_query_tool():
    body = request.json
    return_type = body.get("return_type", "csv")
    dirty_dois_list = body["dois"]

    clean_dois = [clean_doi(dirty_doi, return_none_if_error=True) for dirty_doi in dirty_dois_list]
    clean_dois = [doi for doi in clean_dois if doi]

    q = db.session.query(pub.Pub.response_jsonb).filter(pub.Pub.id.in_(clean_dois))
    rows = q.all()
    pub_responses = [row[0] for row in rows]

    # save jsonl
    with open("output.jsonl", 'wb') as f:
        for response_jsonb in pub_responses:
            f.write(json.dumps(response_jsonb, sort_keys=True))
            f.write("\n")

    # save csv
    csv_dicts = [pub.csv_dict_from_response_dict(my_dict) for my_dict in pub_responses]
    csv_dicts = [my_dict for my_dict in csv_dicts if my_dict]
    fieldnames = sorted(csv_dicts[0].keys())
    fieldnames = ["doi"] + [name for name in fieldnames if name != "doi"]
    with open("output.csv", 'wb') as f:
        writer = unicodecsv.DictWriter(f, fieldnames=fieldnames, dialect='excel')
        writer.writeheader()
        for my_dict in csv_dicts:
            writer.writerow(my_dict)

    # prep email
    email_address = body["email"]
    email = create_email(email_address,
                 "Your Unpaywall results",
                 "simple_query_tool",
                 {"profile": {}},
                 ["output.csv", "output.jsonl"])
    send(email, for_real=True)

    # @todo make sure in the return dict that there is a row for every doi
    # even those not in our db
    return jsonify({"got it": email_address, "dois": clean_dois})


@app.route("/feed/changefiles", methods=["GET"])
def get_changefiles():
    # api key is optional here, is just sends back urls that populate with it
    api_key = request.args.get("api_key", "YOUR_API_KEY")
    resp = get_changefile_dicts(api_key)
    return jsonify({"list": resp})

@app.route("/feed/changefile/<path:filename>", methods=["GET"])
def get_changefile_filename(filename):
    api_key = request.args.get("api_key", None)
    if not api_key:
        abort_json(401, "You must provide an API_KEY")
    if api_key not in valid_changefile_api_keys():
        abort_json(403, "Invalid api_key")

    key = get_file_from_bucket(filename, api_key)
    # streaming response, see https://stackoverflow.com/q/41311589/596939
    return Response(key, content_type="gzip")


@app.route("/search/<path:query>", methods=["GET"])
def get_search_query(query):
    start_time = time()
    my_pubs = fulltext_search_title(query)
    response = [my_pub.to_dict_search() for my_pub in my_pubs]
    sorted_response = sorted(response, key=lambda k: k['score'], reverse=True)
    elapsed_time = elapsed(start_time, 3)
    return jsonify({"results": sorted_response, "elapsed_seconds": elapsed_time})

@app.route("/search/autocomplete/<path:query>", methods=["GET"])
def get_search_autocomplete_query(query):
    start_time = time()
    response = autocomplete_phrases(query)
    sorted_response = sorted(response, key=lambda k: k['score'], reverse=True)
    elapsed_time = elapsed(start_time, 3)
    return jsonify({"results": sorted_response, "elapsed_seconds": elapsed_time})

@app.route("/admin/restart/<api_key>", methods=["GET"])
def restart_endpoint(api_key):
    print "in restart endpoint"
    if api_key != os.getenv("HEROKU_API_KEY"):
        print u"not allowed to reboot in restart_endpoint"
        return jsonify({
            "response": "not allowed to reboot, didn't send right heroku api key"
        })

    dyno_prefix = "run_page."
    restart_dynos("oadoi", dyno_prefix)

    return jsonify({
        "response": "restarted dynos: {}".format(dyno_prefix)
    })

@app.route("/admin/accuracy", methods=["GET"])
def accuracy_report():
    reports = []
    subset_q = "select distinct input_batch_name from accuracy_from_mturk"
    subsets = get_sql_answers(db, subset_q)
    # subsets = ["articlelike_all_years"]

    for subset in subsets:
        reports.append(AccuracyReport(test_set=subset, no_rg_or_academia=True))
        reports.append(AccuracyReport(test_set=subset, genre='journal-article', no_rg_or_academia=True))
        reports.append(AccuracyReport(test_set=subset, since_2017=True, no_rg_or_academia=True))
        reports.append(AccuracyReport(test_set=subset, before_2008=True, no_rg_or_academia=True))

    for report in reports:
        report.build_current_report()

    return jsonify({"response": [report.to_dict() for report in reports]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)

















