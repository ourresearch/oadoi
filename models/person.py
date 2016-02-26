from sqlalchemy.dialects.postgresql import JSONB

from app import db

from datetime import datetime
from datetime import timedelta
import jwt
import twitter
import os
import shortuuid


def make_person_from_google(person_dict):
    print "\n\nmaking new person with person_dict: ", person_dict, "\n\n"
    new_person = Person(
        email=person_dict["email"],
        given_name=person_dict["given_name"],
        family_name=person_dict["family_name"],
        picture=person_dict["picture"],
        oauth_source='google',
        oauth_api_raw=person_dict
    )

    db.session.add(new_person)
    db.session.commit()

    return new_person


class Person(db.Model):
    id = db.Column(db.Text, primary_key=True)
    orcid_id = db.Column(db.Text)
    email = db.Column(db.Text)
    given_name = db.Column(db.Text)
    family_name = db.Column(db.Text)
    picture = db.Column(db.Text)

    oauth_source = db.Column(db.Text)
    oauth_api_raw = db.Column(JSONB)

    def __init__(self, **kwargs):
        shortuuid.set_alphabet('abcdefghijklmnopqrstuvwxyz1234567890')
        self.id = shortuuid.uuid()[0:24]
        super(Person, self).__init__(**kwargs)

    def to_dict(self):
        return {
            "email": self.email,
            "given_names": self.given_name,
            "family_name": self.family_name,
            "picture": self.picture,
            "orcid_id": self.orcid_id
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




