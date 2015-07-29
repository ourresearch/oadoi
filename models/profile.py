from app import db
from models.repo import create_repo
from models.repo import Repo
from providers import github
from util import dict_from_dir

from sqlalchemy.dialects.postgresql import JSON
import datetime
import logging

logger = logging.getLogger("profile")


def create_profile(username):
    profile_data = github.get_profile_data(username)
    profile = Profile(username=username, github_data=profile_data)

    repo_data = github.get_all_repo_data(username)
    for repo_dict in repo_data:
        repo = create_repo(username, repo_dict["name"], repo_dict)
        profile.repos.append(repo)
    db.session.merge(profile)
    db.session.commit()
    return profile


class Profile(db.Model):
    username = db.Column(db.Text, primary_key=True)
    created = db.Column(db.DateTime())
    github_data = db.Column(JSON)

    repos = db.relationship(
        'Repo',
        lazy='subquery',
        cascade='all, delete-orphan',
        backref=db.backref("repo", lazy="subquery")
    )

    def __init__(self, **kwargs):
        super(Profile, self).__init__(**kwargs)
        self.created = datetime.datetime.utcnow().isoformat()

    @property
    def name(self):
        return self.github_data["name"]

    def __repr__(self):
        return u'<Profile {username}>'.format(
            username=self.username)


    def display_dict(self, keys_to_show="all"):
        keys_to_return = [
            "avatar_url",
            "bio",
            "blog",
            "company",
            "created_at",
            "email",
            "followers",
            "following",
            "gravatar_id",
            "html_url",
            "login",
            "location",
            "name",
            "organizations_url",
            "public_gists",
            "public_repos",
            "received_events_url",
            "repos_url",
            "updated_at"
            ]
        smaller_dict = dict([(k, self.github_data[k]) for k in keys_to_return if k in self.github_data])
        smaller_dict["repos"] = [repo.display_dict() for repo in self.repos]
        return smaller_dict

    def to_dict(self, keys_to_show="all"):

        if keys_to_show=="all":
            attributes_to_ignore = ["repos"]
            ret = dict_from_dir(self, attributes_to_ignore)
        else:
            ret = dict_from_dir(self, keys_to_show=keys_to_show)

        return ret
