from app import app
# from app import db

import article

from flask import make_response
from flask import request
from flask import redirect
from flask import abort
from flask import render_template
from flask import jsonify

import json
import os
import logging
import sys
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
def redirect_www_to_naked_domain():
    if request.url.startswith("http://www.sherlockoa.org"):

        new_url = request.url.replace(
            "http://www.sherlockoa.org",
            "http://sherlockoa.org"
        )
        return redirect(new_url, 301)  # permanent




@app.route('/tests')
def tests_endpoint():
    my_tests = article.Tests()
    my_tests.run()
    return render_template(
        'tests.html',
        tests=my_tests
    )

@app.route('/')
def index_endpoint():
    return render_template(
        'index.html'
    )


# can call with ?set_license_even_if_not_oa=True
@app.route("/article/<host>/<path:url>", methods=["GET"])
def get_article_endpoint(host, url):
    my_article = article.Article(url, host)
    set_license_even_if_not_oa = request.args.get("set_license_even_if_not_oa", False)
    my_article.set_is_oa_and_license(set_license_even_if_not_oa)
    return jsonify({"results": my_article.to_dict()})


# can call with ?set_license_even_if_not_oa=True
@app.route("/articles", methods=["POST"])
def post_articles_endpoint():
    article_tuples = request.json
    set_license_even_if_not_oa = request.args.get("set_license_even_if_not_oa", False)
    my_articles = article.get_oa_in_parallel(article_tuples, set_license_even_if_not_oa)
    return jsonify({"results": [a.to_dict() for a in my_articles]})



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5010))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)

















