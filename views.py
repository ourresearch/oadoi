from flask import make_response
from flask import request
from flask import redirect
from flask import abort
from flask import render_template
from flask import jsonify
from flask import g
from flask import url_for

import json
import os
import sys
import requests
from time import time
from datetime import datetime
import unicodecsv
from io import BytesIO

from app import app
from app import db
from app import logger

import pub
import repository
from emailer import send
from gs import get_gs_cache
from gs import post_gs_cache
from util import NoDoiException
from util import safe_commit
from util import restart_dyno
from util import elapsed
from util import clean_doi




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
    if request.endpoint != "get_doi_endpoint":
        return

    logging_start_time = time()

    try:
        results = json.loads(resp.get_data())["results"][0]
    except (ValueError, RuntimeError, KeyError):
        # don't bother logging if no results
        return

    oa_color = results["oa_color"]
    if not oa_color:
        oa_color = "gray"

    body = {
        "timestamp": datetime.utcnow().isoformat(),
        "elapsed": elapsed(g.request_start_time, 2),
        "ip": get_ip(),
        "status_code": resp.status_code,
        "email": request.args.get("email", None),
        "doi": results["doi"],
        "year": results.get("year", None),
        "oa_color": oa_color
    }

    h = {
        "content-type": "text/json",
        "X-Forwarded-For": get_ip()
    }

    url = "http://logs-01.loggly.com/inputs/6470410b-1d7f-4cb2-a625-72d8fa867d61/tag/{}/".format(
        oa_color)
    requests.post(url, headers=h, data=json.dumps(body))
    # logger.info(u"log_request took {} seconds".format(elapsed(logging_start_time, 2)))


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


@app.route("/data/sources/<query_string>", methods=["GET"])
def sources_endpoint(query_string):
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
def post_dois():
    body = request.json
    dirty_dois_list = body["dois"]

    print "dois: before doi clean with {} dois".format(len(dirty_dois_list))

    clean_dois = [clean_doi(dirty_doi, return_none_if_error=True) for dirty_doi in dirty_dois_list]
    clean_dois = [doi for doi in clean_dois if doi]

    q = db.session.query(pub.Pub).filter(pub.Pub.id.in_(clean_dois))
    pubs = q.all()

    csvfile = "output.csv"
    csv_dicts = [my_pub.to_dict_csv() for my_pub in pubs]
    csv_dicts = [my_dict for my_dict in csv_dicts if my_dict]
    fieldnames = sorted(csv_dicts[0].keys())
    fieldnames = ["doi"] + [name for name in fieldnames if name != "doi"]
    with open(csvfile, 'wb') as f:
        writer = unicodecsv.DictWriter(f, fieldnames=fieldnames, dialect='excel')
        writer.writeheader()
        for my_pub in pubs:
            writer.writerow(my_pub.to_dict_csv())

    print "dois: after csv with {} pubs".format(len(pubs))

    email_address = body["email"]
    send(email_address,
         "Your Unpaywall results",
         "check-dois",
         {"profile": {}},
         attachment = csvfile,
         for_real=True)

    print "dois: email sent"
    # @todo make sure in the return dict that there is a row for every doi
    # even those not in our db
    return jsonify({"got it": email_address, "dois": clean_dois, "pubs":[my_pub.to_dict_csv() for my_pub in pubs]})


@app.route("/gs/cache/<path:doi>", methods=["GET"])
def get_gs_cache_endpoint(doi):
    my_gs = get_gs_cache(doi)
    if not my_gs:
        return abort_json(404, "url not found")
    return jsonify(my_gs.to_dict())


@app.route("/gs/cache", methods=["POST"])
def post_gs_cache_endpoint():
    body = request.json
    my_gs = post_gs_cache(**body)
    return jsonify(my_gs.to_dict())



@app.route("/admin/restart", methods=["POST"])
def restart_endpoint():
    logger.info(u"in restart endpoint")
    allowed_to_reboot = False
    for (k, v) in request.args.iteritems():
        if v==os.getenv("HEROKU_API_KEY"):
            allowed_to_reboot = True
    if not allowed_to_reboot:
        logger.info(u"not allowed to reboot in restart_endpoint")
        return jsonify({
            "response": "not allowed to reboot, didn't send right heroku api key"
        })

    payload_json = json.loads(request.form["payload"])

    dynos_to_restart = set()
    for event in payload_json["events"]:
        logger.info(u"dyno {}".format(event["program"]))
        dyno_name = event["program"].split("/")[1]
        dynos_to_restart.add(dyno_name)

    # just restart each dyno once
    logger.info(u"restarting dynos: {}".format(dynos_to_restart))
    for dyno_name in dynos_to_restart:
        restart_dyno("oadoi", dyno_name)

    return jsonify({
        "response": "restarted dynos: {}".format(dynos_to_restart)
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)

















