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
import logging
import sys
import datetime

from app import app
from app import db

import publication
from util import NoDoiException
from util import safe_commit


logger = logging.getLogger("views")


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

    return resp



@app.before_request
def stuff_before_request():

    g.refresh = True
    # g.refresh = False
    # if ('refresh', u'') in request.args.items():
    #     g.refresh = True
    #     print "REFRESHING THIS PUBLICATION IN THE DB"

    # don't redirect http api
    if request.url.startswith("http://api."):
        return


    # redirect everything else to https.
    new_url = None
    try:
        if request.headers["X-Forwarded-Proto"] == "https":
            pass
        elif "http://" in request.url:
            new_url = request.url.replace("http://", "https://")
    except KeyError:
        # print "There's no X-Forwarded-Proto header; assuming localhost, serving http."
        pass

    # redirect to naked domain from www
    if request.url.startswith("https://www.oadoi.org"):
        new_url = request.url.replace(
            "https://www.oadoi.org",
            "https://oadoi.org"
        )
        print u"URL starts with www; redirecting to " + new_url

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

    print u"in get_multiple_pubs_response with {}".format(biblios)


    force_refresh = g.refresh
    if is_person_who_is_making_too_many_requests:
        print u"is_person_who_is_making_too_many_requests, so returning 429"
        abort_json(429, u"sorry, you are calling us too quickly.  Please email team@impactstory.org so we can figure out a good way to get you the data you are looking for.")
    pubs = publication.get_pubs_from_biblio(biblios, force_refresh)
    return pubs


def get_pub_from_doi(doi):
    force_refresh = g.refresh
    try:
        my_pub = publication.get_pub_from_biblio({"doi": doi}, force_refresh)
    except NoDoiException:
        abort_json(404, u"'{}' is an invalid doi.  See http://doi.org/{}".format(doi, doi))
    return my_pub

@app.route("/v1/publication/doi/<path:doi>", methods=["GET"])
@app.route("/v1/publication/doi.json/<path:doi>", methods=["GET"])
def get_from_new_doi_endpoint(doi):
    my_pub = get_pub_from_doi(doi)
    return jsonify({"results": [my_pub.to_dict()]})


def print_ip():
    user_agent = request.headers.get('User-Agent')
    # from http://stackoverflow.com/a/12771438/596939
    if request.headers.getlist("X-Forwarded-For"):
       ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
       ip = request.remote_addr
    print u"calling from IP {ip}. User-Agent is '{user_agent}'.".format(
        ip=ip,
        user_agent=user_agent
    )


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
    return jsonify({"results": [p.to_dict() for p in pubs]})



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
    force_refresh = g.refresh
    print "request_biblio", request_biblio
    my_pub = publication.get_pub_from_biblio(request_biblio, force_refresh)
    return json_resp({"results": [my_pub.to_dict()]})




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
def index_endpoint():
    if request.method == "POST":
        print_ip()
        pubs = get_multiple_pubs_response()
        return jsonify({"results": [p.to_dict() for p in pubs]})

    if "://api." in request.url:
        return jsonify({
            "version": "1.1.0",
            "documentation_url": "https://oadoi.org/api",
            "msg": "Don't panic"
        })
    else:
        return render_template(
            'index.html'
        )


#  does three things:
#   the api response for GET /:doi
#   the (angular) web app, which handles all web pages
#   the DOI resolver (redirects to article)


@app.route("/<path:doi>", methods=["GET"])
def get_doi_redirect_endpoint(doi):

    # the GET api endpoint (returns json data)
    if "://api." in request.url and "/admin/" not in request.url:
        my_pub = get_pub_from_doi(doi)
        return jsonify({"results": [my_pub.to_dict()]})

    # the web interface (returns an SPA webpage that runs AngularJS)
    if not doi or not doi.startswith("10."):
        return index_endpoint()  # serve the angular app

    # the DOI resolver (returns a redirect)
    my_pub = get_pub_from_doi(doi)
    return redirect(my_pub.best_redirect_url, 302)  # 302 is temporary redirect


@app.route("/admin/restart", methods=["POST"])
def restart_endpoint():
    print "in restart endpoint"
    print "request.args.items():", request.args.items()
    print "request.form", request.form
    print 'request.headers', request.headers
    return jsonify({
        "response": "rebooted!"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)

















