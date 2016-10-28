from flask import make_response
from flask import request
from flask import redirect
from flask import abort
from flask import render_template
from flask import jsonify
from flask import g

import json
import os
import logging
import sys

from app import app

import product
import oa_scrape


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


#support CORS
@app.after_request
def add_crossdomain_header(resp):
    resp.headers['Access-Control-Allow-Origin'] = "*"
    resp.headers['Access-Control-Allow-Methods'] = "POST, GET, OPTIONS, PUT, DELETE, PATCH"
    resp.headers['Access-Control-Allow-Headers'] = "origin, content-type, accept, x-requested-with"

    # without this jason's heroku local buffers forever
    sys.stdout.flush()

    return resp



@app.before_request
def redirects():

    g.use_cache = True
    if ('no-cache', u'') in request.args.items():
        g.use_cache = False
        print "NOT USING CACHE"

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



@app.route('/tests')
def tests_endpoint():
    my_tests = oa_scrape.Tests()
    my_tests.run()
    return render_template(
        'tests.html',
        tests=my_tests
    )




@app.route("/v1/publication/doi/<path:doi>", methods=["GET"])
def get_publication_doi_endpoint(doi):
    request_biblio = {"doi": doi}
    my_collection = product.run_collection_from_biblio(g.use_cache, **request_biblio)
    return jsonify({"results": my_collection.to_dict()})


@app.route("/v1/publication", methods=["GET"])
def get_publication_biblio_endpoint():
    request_biblio = {}
    for (k, v) in request.args.iteritems():
        request_biblio[k] = v
    my_collection = product.run_collection_from_biblio(g.use_cache, **request_biblio)
    return jsonify({"results": my_collection.to_dict()})


@app.route("/v1/publications", methods=["POST"])
def post_publications_endpoint():
    products = []
    body = request.json
    if "dois" in body:
        if len(body["dois"]) > 25:
            abort_json(413, "max number of DOIs is 25")
        for doi in body["dois"]:
            products += [product.build_product(g.use_cache, **{"doi": doi})]

    elif "biblios" in body:
        for biblio in body["biblios"]:
            products += [product.build_product(g.use_cache, **biblio)]

    my_collection = product.Collection()
    my_collection.products = products
    my_collection.set_fulltext_urls()
    return jsonify({"results": my_collection.to_dict()})




@app.route('/')
def index_endpoint():
    if "//:api." in request.url:
        return jsonify({
            "version": "1.0.0",
            "documentation_url": "https://oadoi.org/api",
            "answer": 42
        })
    else:
        return render_template(
            'index.html'
        )




@app.route("/<path:doi>", methods=["GET"])
def get_doi_redirect_endpoint(doi):
    if not doi or not doi.startswith("10."):
        return index_endpoint()  # serve the angular app

    request_biblio = {"doi": doi}
    my_collection = product.run_collection_from_biblio(g.use_cache, **request_biblio)
    my_product = my_collection.products[0]
    return redirect(my_product.best_redirect_url, 302)  # 302 is temporary redirect


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)

















