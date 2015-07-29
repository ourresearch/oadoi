from app import db
from sqlalchemy.dialects.postgresql import JSON
import datetime
import shortuuid
import logging

from util import dict_from_dir

logger = logging.getLogger("snap")


class Snap(db.Model):
    snap_id = db.Column(db.Text, primary_key=True)    
    repo_id = db.Column(db.Text, db.ForeignKey("repo.repo_id", onupdate="CASCADE", ondelete="CASCADE"))    
    provider = db.Column(db.Text)
    data = db.Column(JSON)
    collected = db.Column(db.DateTime())

    def __init__(self, **kwargs):
        if not "snap_id" in kwargs:
            self.snap_id = shortuuid.uuid()                 
        self.collected = datetime.datetime.utcnow().isoformat()
        super(Snap, self).__init__(**kwargs)

    def __repr__(self):
        return u'<Snap {snap_id} {repo_id} {provider}>'.format(
            snap_id=self.snap_id, repo_id=self.repo_id, provider=self.provider)

    def display_dict(self):
        keys_to_return = [
            "created_at",
            "description",
            "forks_count",
            "language",
            "name",
            "stargazers_count",
            "watchers_count"
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