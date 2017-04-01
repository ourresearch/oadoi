import shortuuid
import datetime
from sqlalchemy import nullslast

from app import db
from util import clean_doi
from util import safe_commit

def get_gs_cache(dirty_doi):
    my_doi = clean_doi(dirty_doi)

    # return the best one we've got
    my_gs = Gs.query.filter(Gs.doi==my_doi).order_by(nullslast(Gs.url)).first()
    if my_gs:
        my_gs.num_hits +=1
        safe_commit(db)
    return my_gs


def post_gs_cache(dirty_doi, my_url):
    my_doi = clean_doi(dirty_doi)
    my_gs = Gs.query.filter(Gs.doi==my_doi, Gs.url==my_url).first()
    if not my_gs:
        my_gs = Gs(doi=my_doi, url=my_url)
        db.session.add(my_gs)
        safe_commit(db)
    return my_gs


class Gs(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text)
    url = db.Column(db.Text)
    created = db.Column(db.DateTime)
    num_hits = db.Column(db.Numeric, default=0)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow()
        super(Gs, self).__init__(**kwargs)

    def __repr__(self):
        return u"<GS ({}) {} {}>".format(self.id, self.doi, self.url)

    def to_dict(self):
        response = {
            "doi": self.doi,
            "url": self.url,
        }
        return response
