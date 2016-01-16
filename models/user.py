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


class User(db.Model):
    screen_name = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    profile_image_url = db.Column(db.Text)
    description = db.Column(db.Text)
    api_raw = db.Column(JSONB)

    oauth_token = db.Column(db.Text)
    oauth_token_secret = db.Column(db.Text)


    def to_dict(self):
        return {
            "screen_name": self.screen_name,
            "name": self.name,
            "profile_image_url": self.profile_image_url,
            "description": self.description
        }

    def get_token(self):
        payload = {
            'sub': self.screen_name,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(days=999),
            'profile_image_url': self.profile_image_url,
            'screen_name': self.screen_name
        }
        token = jwt.encode(payload, os.getenv("JWT_KEY"))
        return token.decode('unicode_escape')




