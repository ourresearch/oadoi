from app import db
import requests
from models import product

def get_orcid_api_raw(orcid):
    headers = {'Accept': 'application/orcid+json'}
    url = "http://pub.orcid.org/{id}/orcid-profile".format(id=orcid)
    r = requests.get(url, headers=headers)
    orcid_resp_dict = r.json()
    return orcid_resp_dict["orcid-profile"]

def add_profile(orcid):

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


    # return {
    #     "given_names": given_names,
    #     "family_name": family_name,
    #     "email": email,
    #     "works": works
    # }

    my_profile = Profile(
        id=orcid,
        given_names=given_names,
        family_name=family_name,
        api_raw=api_raw
    )
    # db.session.merge(my_profile)
    # db.session.commit()
    return my_profile

class Profile(db.Model):
    id = db.Column(db.Text, primary_key=True)
    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    api_raw = db.Column(db.Text)

    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("profile", lazy="subquery")
    )

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




