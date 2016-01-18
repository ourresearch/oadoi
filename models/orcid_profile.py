from sqlalchemy.dialects.postgresql import JSONB

from app import db
from models import provider

import os
import requests


def add_orcid_profile(**kwargs):
    my_profile = OrcidProfile(**kwargs)
    db.session.merge(my_profile)
    db.session.commit()  
    return my_profile


class OrcidProfile(db.Model):
    id = db.Column(db.Text, primary_key=True)
    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    created = db.Column(db.DateTime())
    modified = db.Column(db.DateTime())
    created_method = db.Column(db.Text)
    num_works = db.Column(db.Integer)
    num_all_dois = db.Column(db.Integer)
    num_dois_since_2010 = db.Column(db.Integer)
    dois = db.Column(JSONB)

    def __repr__(self):
        return u'<OrcidProfile ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names, 
            family_name=self.family_name
        )




