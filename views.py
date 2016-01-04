from app import app

from models.article import add_article
from models.user import User
from models.user import make_user

from flask import make_response
from flask import request
from flask import abort
from flask import jsonify
from flask import render_template

import jwt
from jwt import DecodeError
from jwt import ExpiredSignature
from functools import wraps

import requests
from requests_oauthlib import OAuth1


import os
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
# from satellizer.
# move to another file later
# this is copied from early GitHub-login version of Depsy. It's here:
# https://github.com/Impactstory/depsy/blob/ed80c0cb945a280e39089822c9b3cefd45f24274/views.py
###########################################################################




def parse_token(req):
    token = req.headers.get('Authorization').split()[1]
    return jwt.decode(token, app.config['JWT_KEY'])


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

        g.current_user_username = payload['sub']

        return f(*args, **kwargs)

    return decorated_function











###########################################################################
# API
###########################################################################
@app.route("/api")
def api_test():
    return jsonify({"resp": "Impactstory: The Next Generation."})


@app.route("/api/doi/<path:doi>")
@app.route("/api/doi/<path:doi>.json")
def get_doi(doi):

    resp = {"doi": doi}
    my_article = add_article(doi)
    resp["plos_metrics"] = my_article.plos_metrics()
    resp["crossref_deets"] = my_article.crossref_deets()
    resp["altmetric_metrics"] = my_article.altmetric_metrics()
        
    return jsonify(resp)



# user management
##############################################################################

@app.route('/auth/twitter', methods=['POST'])
def twitter():
    request_token_url = 'https://api.twitter.com/oauth/request_token'
    access_token_url = 'https://api.twitter.com/oauth/access_token'

    if request.json.get('oauth_token') and request.json.get('oauth_verifier'):

        # the user already has some creds from signing in to twitter.
        # now get the users's twitter login info.

        auth = OAuth1(os.getenv('TWITTER_CONSUMER_KEY'),
                      client_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
                      resource_owner_key=request.json.get('oauth_token'),
                      verifier=request.json.get('oauth_verifier'))

        r = requests.post(access_token_url, auth=auth)
        profile = dict(parse_qsl(r.text))

        # get an impactstory user object from the login info we just got from twitter
        my_user = User.query.get(profile['screen_name'])

        # if we don't have this user, make it
        if my_user is None:
            my_user = make_user(
                profile["screen_name"],
                profile["oauth_token"],
                profile["oauth_token_secret"]
            )

        # Regardless of whether we made a new user or retrieved an old one,
        # return an updated token
        token = my_user.get_token()
        return jsonify(token=token)

    else:
        # we are just starting the whole process. give them the info to
        # help them sign in on the redirect twitter window.
        oauth = OAuth1(
            os.getenv('TWITTER_CONSUMER_KEY'),
            client_secret=os.getenv('TWITTER_CONSUMER_SECRET'),
            callback_uri="http://localhost:5000/login"
        )

        r = requests.post(request_token_url, auth=oauth)
        oauth_token = dict(parse_qsl(r.text))
        return jsonify(oauth_token)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)





