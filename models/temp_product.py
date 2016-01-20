from sqlalchemy.dialects.postgresql import JSONB

from app import db
from models import provider

import os
import requests
import shortuuid

class TempProduct(db.Model):
    orcid = db.Column(db.Text, db.ForeignKey('temp_orcid_profile.id'))
    doi = db.Column(db.Text)
    id = db.Column(db.Text, primary_key=True)
    title = db.Column(db.Text)
    year = db.Column(db.Text)
    created = db.Column(db.DateTime())
    work_type = db.Column(db.Text)

    def __init__(self, **kwargs):
        shortuuid.set_alphabet('abcdefghijklmnopqrstuvwxyz1234567890')
        self.id = shortuuid.uuid()[0:24]
        super(TempProduct, self).__init__(**kwargs)

    def __repr__(self):
        return u'<TempProduct ({orcid} {doi}) >'.format(
            orcid=self.orcid,
            doi=self.doi
        )




