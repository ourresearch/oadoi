from sqlalchemy.dialects.postgresql import JSONB

from app import db

from datetime import datetime
from datetime import timedelta
import jwt
import twitter
import os

def make_user(screen_name, oauth_token, oauth_token_secret):
    api = twitter.Api(
        consumer_key=os.getenv('TWITTER_CONSUMER_KEY'),
        consumer_secret=os.getenv('TWITTER_CONSUMER_SECRET'),

        # maybe we are supposed to use our own tokens here, not a user's. works tho.
        access_token_key=oauth_token,
        access_token_secret=oauth_token_secret
    )

    # get all of twitter's information for @screen_name
    api_raw = api.GetUser(screen_name=screen_name)

    new_user = User(
        screen_name=api_raw.screen_name,
        name=api_raw.name,
        profile_image_url=api_raw.profile_image_url,
        description=api_raw.description,
        api_raw=api_raw.AsDict(),
        oauth_token=oauth_token,
        oauth_token_secret=oauth_token_secret
    )

    db.session.add(new_user)
    db.session.commit()

    return new_user


def make_user_from_google(profile_dict):
    print "\n\nmaking new user with profile_dict: ", profile_dict, "\n\n"
    new_user = User(
        email=profile_dict["email"],
        given_name=profile_dict["given_name"],
        family_name=profile_dict["family_name"],
        picture=profile_dict["picture"],
        oauth_source='google',
        oauth_api_raw=profile_dict
    )

    db.session.add(new_user)
    db.session.commit()

    return new_user


class User(db.Model):
    email = db.Column(db.Text, primary_key=True)
    given_name = db.Column(db.Text)
    family_name = db.Column(db.Text)
    picture = db.Column(db.Text)

    orcid = db.Column(db.Text)

    oauth_source = db.Column(db.Text)
    oauth_api_raw = db.Column(JSONB)

    __tablename__ = 'ti_user'

    def to_dict(self):
        return {
            "email": self.email,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "picture": self.picture
        }

    def get_token(self):
        payload = {
            'sub': self.email,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(days=999),
            'picture': self.picture
        }
        token = jwt.encode(payload, os.getenv("JWT_KEY"))
        return token.decode('unicode_escape')




