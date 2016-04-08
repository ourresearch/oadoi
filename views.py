from app import app
from app import db

from models.person import Person
from models.person import make_person
from models.person import set_person_email
from models.person import set_person_claimed_at
from models.person import pull_from_orcid
from models.person import add_or_overwrite_person_from_orcid_id
from models.person import delete_person
from models.badge import badge_configs_without_functions
from models.search import autocomplete
from models.url_slugs_to_redirect import url_slugs_to_redirect

from flask import make_response
from flask import request
from flask import redirect
from flask import abort
from flask import jsonify
from flask import render_template
from flask import g

import jwt
from jwt import DecodeError
from jwt import ExpiredSignature
from functools import wraps

import requests
import stripe
from requests_oauthlib import OAuth1


import os
import time
import json
import logging
from urlparse import parse_qs, parse_qsl

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
    # hide_keys = request.args.get("hide", "").split(",")
    # if hide_keys:
    #     for key_to_hide in hide_keys:
    #         try:
    #             del thing[key_to_hide]
    #         except KeyError:
    #             pass

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

    if page.lower() in url_slugs_to_redirect:
        return redirect(u"http://v1.impactstory.org/{}".format(page.strip()), code=302)

    return render_template(
        'index.html',
        is_local=os.getenv("IS_LOCAL", False),
        stripe_publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY")
    )



@app.before_request
def redirect_to_https():
    try:
        if request.headers["X-Forwarded-Proto"] == "https":
            pass
        else:
            return redirect(request.url.replace("http://", "https://"), 301)  # permanent
    except KeyError:
        #logger.debug(u"There's no X-Forwarded-Proto header; assuming localhost, serving http.")
        pass


@app.before_request
def redirect_www_to_naked_domain():
    if request.url.startswith("https://www.impactstory.org"):

        new_url = request.url.replace(
            "https://www.impactstory.org",
            "https://impactstory.org"
        )
        logger.debug(u"URL starts with www; redirecting to " + new_url)
        return redirect(new_url, 301)  # permanent





###########################################################################
# from satellizer.
# move to another file later
# this is copied from early GitHub-login version of Depsy. It's here:
# https://github.com/Impactstory/depsy/blob/ed80c0cb945a280e39089822c9b3cefd45f24274/views.py
###########################################################################




def parse_token(req):
    token = req.headers.get('Authorization').split()[1]
    return jwt.decode(token, os.getenv("JWT_KEY"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.headers.get('Authorization'):
            response = jsonify(message='Missing authorization header')
            response.status_code = 401
            return response

        try:
            payload = parse_token(request)
        except DecodeError:
            response = jsonify(message='Token is invalid')
            response.status_code = 401
            return response
        except ExpiredSignature:
            response = jsonify(message='Token has expired')
            response.status_code = 401
            return response

        g.me_orcid_id = payload['sub']

        return f(*args, **kwargs)

    return decorated_function











###########################################################################
# API
###########################################################################
@app.route("/api")
def api_test():
    return json_resp({"resp": "Impactstory: The Next Generation."})


@app.route("/api/search/<search_str>")
def search(search_str):
    ret = autocomplete(search_str)
    return jsonify({"list": ret, "count": len(ret)})


@app.route("/api/test")
def test0():
    return jsonify({"test": True})



@app.route("/api/people")
def people_endpoint():
    time.sleep(.5)
    count = 17042
    return jsonify({"count": count})

@app.route("/api/badges")
def badges_about():
    return json_resp(badge_configs_without_functions())


@app.route("/api/person/assign/<orcid_id>")
@app.route("/api/person/assign/<orcid_id>.json")
def api_assign_badges(orcid_id):
    from sqlalchemy import orm
    my_person = Person.query.options(orm.undefer('*')).filter_by(orcid_id=orcid_id).first()
    my_person.assign_badges()
    return json_resp(my_person.to_dict())


@app.route("/api/person/<orcid_id>")
@app.route("/api/person/<orcid_id>.json")
def profile_endpoint(orcid_id):
    my_person = Person.query.filter_by(orcid_id=orcid_id).first()
    if not my_person:
        abort_json(404, "that profile doesn't exist")

    return json_resp(my_person.to_dict())


# for testing.  make an impactstory profile from an orcid_id
@app.route("/api/person/<orcid_id>", methods=['POST'])
@app.route("/api/person/<orcid_id>/create")
def person_create(orcid):
    my_profile = add_or_overwrite_person_from_orcid_id(orcid_id, high_priority=True)
    return json_resp(my_profile.to_dict())



@app.route("/api/donation", methods=["POST"])
def donation_endpoint():
    stripe.api_key = os.getenv("STRIPE_API_KEY")
    metadata = {
        "full_name": request.json["fullName"],
        "orcid_id": request.json["orcidId"],
        "email": request.json["email"]
    }
    try:
        stripe.Charge.create(
            amount=request.json["cents"],
            currency="usd",
            source=request.json["tokenId"],
            description="Impactstory donation",
            metadata=metadata
        )
    except stripe.error.CardError, e:
        # The card has been declined
        abort_json(499, "Sorry, your credit card was declined.")

    return jsonify({"message": "well done!"})


# user management
##############################################################################

@app.route("/api/auth/orcid", methods=["POST"])
def orcid_auth():
    access_token_url = 'https://pub.orcid.org/oauth/token'

    payload = dict(client_id="APP-PF0PDMP7P297AU8S",
                   redirect_uri=request.json['redirectUri'],
                   client_secret=os.getenv('ORCID_CLIENT_SECRET'),
                   code=request.json['code'],
                   grant_type='authorization_code')


    # Exchange authorization code for access token
    # The access token has the ORCID ID, which is actually all we need here.
    r = requests.post(access_token_url, data=payload)
    my_orcid_id = r.json()["orcid"]
    my_person = Person.query.filter_by(orcid_id=my_orcid_id).first()

    try:
        token = my_person.get_token()
    except AttributeError:  # my_person is None. So make a new user

        # @todo: make_person() is untested. Test.
        my_person = make_person(my_orcid_id, high_priority=True)
        token = my_person.get_token()

    set_person_claimed_at(my_person)

    return jsonify(token=token)


@app.route('/api/me', methods=["GET", "DELETE", "POST"])
@login_required
def me():
    if request.method == "GET":
        my_person = Person.query.filter_by(orcid_id=g.me_orcid_id).first()
        return jsonify(my_person.to_dict())
    elif request.method == "DELETE":

        delete_person(orcid_id=g.me_orcid_id)
        return jsonify({"msg": "Alas, poor Yorick! I knew him, Horatio"})

    elif request.method == "POST":

        if request.json.get("action", None) == "pull_from_orcid":
            pull_from_orcid(g.me_orcid_id)
            return jsonify({"msg": "pull successful"})

        elif request.json.get("email", None):
            set_person_email(g.me_orcid_id, request.json["email"], True)
            return jsonify({"msg": "email set successfully"})





if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)





