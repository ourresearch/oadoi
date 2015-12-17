from app import app

from models.search import autocomplete
from util import elapsed
from models.person import Person
from models import package
from models.package import Package
from models.github_repo import get_readme
from models.entity import make_badge_io
from models.package_jobs import get_leaders
from models.tags import Tags
from dummy_data import get_dummy_data
from sqlalchemy import orm
from models.package import make_host_name

from flask import make_response
from flask import request
from flask import abort
from flask import jsonify
from flask import send_file
from flask import render_template
from flask import redirect
from flask import url_for

from time import time
import requests

import os
import json
import re

import logging

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


def json_resp_from_thing(thing):
    hide_keys = request.args.get("hide", "").split(",")
    if hide_keys is not None:
        for key_to_hide in hide_keys:
            try:
                del thing[key_to_hide]
            except KeyError:
                pass

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


@app.route("/<path:page>")  # from http://stackoverflow.com/a/14023930/226013
@app.route("/")
def index_view(path="index", page=""):
    return render_template('index.html')















###########################################################################
# API
###########################################################################
@app.route("/api")
def api_test():
    return jsonify({"resp": "Hi, I'm Despy!"})

@app.route("/api/person/<person_id>")
@app.route("/api/person/<person_id>.json")
def person_endpoint(person_id):

    # data = get_dummy_data("person")
    # return json_resp_from_thing(data)

    from models.contribution import Contribution
    my_person = Person.query.options(orm.subqueryload_all(
            Person.contributions, 
            Contribution.package, 
            Package.contributions, 
            Contribution.person 
            # Person.contributions
        )).get(int(person_id))

    if not my_person:
        abort_json(404, "This person's not in the database")

    return json_resp_from_thing(my_person.to_dict())


@app.route("/api/person/<person_id>/badge.svg")
def person_badge(person_id):
    my_person = Person.query.get(int(person_id))
    if not my_person:
        abort_json(404, "This person's not in the database")

    my_badge_file = make_badge_io(my_person)
    return send_file(my_badge_file, mimetype='image/svg+xml')

@app.route("/api/package/<host_or_language>/<project_name>")
@app.route("/api/package/<host_or_language>/<project_name>.json")
def package_endpoint(host_or_language, project_name):

    my_id = package.make_id(host_or_language, project_name)

    from models.contribution import Contribution
    my_package = Package.query.options(
        orm.subqueryload_all(Package.contributions, Contribution.person)
    ).get(my_id)

    if not my_package:
        abort_json(404, "This package is not in the database")

    resp_dict = my_package.to_dict()
    return json_resp_from_thing(resp_dict)


@app.route("/api/package/github/<owner>/<repo_name>")
@app.route("/api/package/github/<owner>/<repo_name>.json")
def github_package_endpoint(owner, repo_name):
    try:
        host, name = package.package_id_from_github_info(owner, repo_name)
    except TypeError:
        return abort_json(404, "We don't know of any CRAN or PyPI package associated with this GitHub repo. Please report errors at team@impactstory.org. Thanks!")

    url = url_for(
        "package_endpoint",
        host_or_language=host,
        project_name=name
    )
    return redirect(url)


@app.route("/api/package/<host_or_language>/<project_name>/badge.svg")
def package_badge(host_or_language, project_name):
    my_id = package.make_id(host_or_language, project_name)
    my_package = Package.query.get(my_id)
    if not my_package:
        abort_json(404, "This package is not in the database")

    my_badge_file = make_badge_io(my_package)
    return send_file(my_badge_file, mimetype='image/svg+xml')

@app.route('/api/leaderboard')
@app.route('/api/leaderboard.json')
def leaderboard():
    filters_dict = make_filters_dict(request.args)
    page_size = request.args.get("page_size", "25")

    start = time()
    num_total, leaders = get_leaders(
        filters=filters_dict,
        page_size=int(page_size)
    )

    leaders_list = [leader.as_snippet for leader in leaders]

    ret_dict = {
        "num_returned": len(leaders_list),
        "num_total": num_total,
        "list": leaders_list,
        "type": filters_dict["type"],
        "filters": filters_dict
    }
    if "tag" in filters_dict:
        tag_obj = Tags.query.filter(Tags.unique_tag==filters_dict["tag"]).first()
        ret_dict["related_tags"] = tag_obj.related_tags

    ret = json_resp_from_thing(ret_dict)
    elapsed_time = elapsed(start)
    ret.headers["x-elapsed"] = elapsed_time
    return ret


@app.route("/api/search/<search_str>")
def search(search_str):
    ret = autocomplete(search_str)
    return jsonify({"list": ret, "count": len(ret)})

@app.route("/test")
def test():
    r = requests.get("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Lawrence_of_arabia_ver3_xxlg.jpg/800px-Lawrence_of_arabia_ver3_xxlg.jpg")


    return r.content



@app.route("/api/readme")
def get_readme_endpoint():
    readme = get_readme("Impactstory", "depsy")
    return jsonify({"readme": readme})


def make_filters_dict(args):
    language = args.get("language", None)
    if language:
        host_name = make_host_name(language)
    else:
        host_name = None

    full_dict = {
        "type": args.get("type", None),
        "is_academic": args.get("only_academic", False),
        "host": host_name,
        "tag": args.get("tag", None)
    }
    ret = {}

    # don't return keys with falsy values, we won't filter by them.
    for k, v in full_dict.iteritems():
        if v:
            ret[k] = v

    return ret





if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5008))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)





