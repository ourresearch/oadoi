import hashlib
import re

from sqlalchemy import and_

from app import db
from endpoint import Endpoint
from repository import Repository


class RepoRequest(db.Model):
    id = db.Column(db.Text, primary_key=True)
    updated = db.Column(db.DateTime)
    email = db.Column(db.Text)
    pmh_url = db.Column(db.Text)
    repo_name = db.Column(db.Text)
    institution_name = db.Column(db.Text)
    examples = db.Column(db.Text)
    repo_home_page = db.Column(db.Text)
    comments = db.Column(db.Text)
    duplicate_request = db.Column(db.Text)

    def __init__(self, **kwargs):
        super(self.__class__, self).__init__(**kwargs)

    # trying to make sure the rows are unique
    def set_id_seed(self, id_seed):
        self.id = hashlib.md5(id_seed).hexdigest()[0:6]

    @classmethod
    def list_fieldnames(self):
        # these are the same order as the columns in the input google spreadsheet
        fieldnames = "id updated email pmh_url repo_name institution_name examples repo_home_page comments duplicate_request".split()
        return fieldnames

    @property
    def is_duplicate(self):
        return self.duplicate_request == "dup"

    @property
    def endpoints(self):
        return []

    @property
    def repositories(self):
        return []

    def matching_endpoints(self):

        response = self.endpoints

        if not self.pmh_url:
            return response

        url_fragments = re.findall('//([^/]+/[^/]+)', self.pmh_url)
        if not url_fragments:
            return response
        matching_endpoints_query = Endpoint.query.filter(Endpoint.pmh_url.ilike("%{}%".format(url_fragments[0])))
        hits = matching_endpoints_query.all()
        if hits:
            response += hits
        return response


    def matching_repositories(self):

        response = self.repositories

        if not self.institution_name or not self.repo_name:
            return response

        matching_query = Repository.query.filter(and_(
            Repository.institution_name.ilike("%{}%".format(self.institution_name)),
            Repository.repository_name.ilike("%{}%".format(self.repo_name))))
        hits = matching_query.all()
        if hits:
            response += hits
        return response


    def to_dict(self):
        response = {}
        for fieldname in RepoRequest.list_fieldnames():
            response[fieldname] = getattr(self, fieldname)
        return response

    def __repr__(self):
        return "<RepoRequest ( {} ) {}>".format(self.id, self.pmh_url)


