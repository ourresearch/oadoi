from app import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from models import product  # needed for sqla i think
from models.product import make_product
from models.product import NoDoiException
from util import elapsed
from time import time

import requests
import json

def get_orcid_api_raw(orcid):
    headers = {'Accept': 'application/orcid+json'}
    url = "http://pub.orcid.org/{id}/orcid-profile".format(id=orcid)
    start = time()
    r = requests.get(url, headers=headers)
    print "got ORCID details in {elapsed}s for {id}".format(
        id=orcid,
        elapsed=elapsed(start)
    )
    orcid_resp_dict = r.json()
    return orcid_resp_dict["orcid-profile"]

def add_profile(orcid, sample_name=None):

    api_raw = get_orcid_api_raw(orcid)

    try:
        given_names = api_raw["orcid-bio"]["personal-details"]["given-names"]["value"]
    except (TypeError,):
        given_names = None

    try:
        family_name = api_raw["orcid-bio"]["personal-details"]["family-name"]["value"]
    except (TypeError,):
        family_name = None

    try:
        email = api_raw["orcid-activities"]["verified-email"]["value"]
    except (KeyError, TypeError):
        email = None

    try:
        works = api_raw["orcid-activities"]["orcid-works"]["orcid-work"]
        if not works:
            works = []
    except TypeError:
        works = []

    my_profile = Profile(
        id=orcid,
        given_names=given_names,
        family_name=family_name,
        api_raw=json.dumps(api_raw)
    )

    for work in works:
        try:
            my_product = make_product(work)
            my_profile.add_product(my_product)
        except NoDoiException:
            # just ignore this work, it's not a product for our purposes.
            pass

    if sample_name:
        my_profile.sample[sample_name] = True

    db.session.merge(my_profile)
    db.session.commit()
    return my_profile

class Profile(db.Model):
    id = db.Column(db.Text, primary_key=True)
    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    api_raw = db.Column(db.Text)
    sample = db.Column(MutableDict.as_mutable(JSONB))

    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("profile", lazy="subquery")
    )

    def add_product(self, product_to_add):
        if self.has_product(product_to_add):
            return False
        else:
            self.products.append(product_to_add)
            return True


    def has_product(self, product_to_test):
        my_titles = [p.title.lower() for p in self.products if p.title]
        my_dois = [p.doi for p in self.products]
        return product_to_test.title in my_titles or product_to_test.doi in my_dois


    def __repr__(self):
        return u'<Profile ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names,
            family_name=self.family_name
        )

    def to_dict(self):
        return {
            "id": self.id,
            "given_names": self.given_names,
            "family_names": self.family_name,
            "products": [p.to_dict() for p in self.products]

        }




