from app import db
from sqlalchemy.dialects.postgresql import JSON
import datetime
import logging

from util import dict_from_dir

logger = logging.getLogger("repo")


class Repo(db.Model):
    username = db.Column(db.Text, db.ForeignKey('profile.username'))    
    reponame = db.Column(db.Text, primary_key=True)
    github_data = db.Column(JSON)

    def __init__(self, **kwargs):
        super(Repo, self).__init__(**kwargs)

    def __repr__(self):
        return u'<Repo {reponame}>'.format(
            reponame=self.reponame)

    def display_dict(self):
        keys_to_return = [
            "created_at",
            "description",
            "forks_count",
            "language",
            "name",
            "stargazers_count"
            ]
        smaller_dict = dict([(k, self.github_data[k]) for k in keys_to_return if k in self.github_data])
        return smaller_dict

    def to_dict(self, keys_to_show="all"):
        if keys_to_show=="all":
            attributes_to_ignore = []
            ret = dict_from_dir(self, attributes_to_ignore)
        else:
            ret = dict_from_dir(self, keys_to_show=keys_to_show)
        return ret