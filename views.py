from app import app
from app import db


from models.profile import add_profile
from models.profile import Profile
from models.orcid import search_orcid
from models.user import User
from models.user import make_user_from_google



from flask import make_response
from flask import request
from flask import abort
from flask import jsonify
from flask import render_template
from flask import g

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
    return render_template('index.html')










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

        g.current_user_email = payload['sub']

        return f(*args, **kwargs)

    return decorated_function











###########################################################################
# API
###########################################################################
@app.route("/api")
def api_test():
    return jsonify({"resp": "Impactstory: The Next Generation."})



@app.route("/api/profile/<orcid>")
def profile_endpoint(orcid):
    my_profile = Profile.query.get(orcid)
    if not my_profile:
        abort_json(404, "that user doesn't exist")

    return jsonify(my_profile.to_dict())


# for testing.  make a profile.
@app.route("/api/profile/<orcid>", methods=['POST'])
@app.route("/api/profile/<orcid>/create")
def profile_create(orcid):
    my_profile = add_profile(orcid)
    return jsonify(my_profile.to_dict())



@app.route("/api/orcid-search")
def orcid_search():
    results_list = search_orcid(
        request.args.get("given_names"),
        request.args.get("family_name")
    )
    return jsonify({"list": results_list})


# user management
##############################################################################


@app.route('/auth/google', methods=['POST'])
def google():

    print "\n\n\n hitting auth/google \n\n\n"

    access_token_url = 'https://accounts.google.com/o/oauth2/token'
    people_api_url = 'https://www.googleapis.com/plus/v1/people/me/openIdConnect'

    payload = dict(client_id=request.json['clientId'],
                   redirect_uri=request.json['redirectUri'],
                   client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                   code=request.json['code'],
                   grant_type='authorization_code')

    # Step 1. Exchange authorization code for access token.
    r = requests.post(access_token_url, data=payload)
    token = r.json()
    headers = {'Authorization': 'Bearer {}'.format(token['access_token'])}

    # Step 2. Retrieve information about the current user.
    r = requests.get(people_api_url, headers=headers)
    google_resp_dict = r.json()

    my_user = User.query.filter_by(email=google_resp_dict['email']).first()

    try:
        token = my_user.get_token()
    except AttributeError:  # make a new user
        my_user = make_user_from_google(google_resp_dict)
        token = my_user.get_token()

    return jsonify(token=token)



@app.route('/api/me')
@login_required
def me():
    my_user = User.query.filter_by(email=g.current_user_email).first()
    return jsonify(my_user.to_dict())


@app.route('/api/me/orcid/<orcid>', methods=['POST'])
@login_required
def set_my_orcid(orcid):
    my_user = User.query.filter_by(email=g.current_user_email).first()
    my_user.orcid = orcid
    db.session.merge(my_user)
    db.session.commit()
    return jsonify(my_user.to_dict())
















if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)





