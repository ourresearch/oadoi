import shortuuid
import datetime
from sqlalchemy.sql.expression import desc
from sqlalchemy.sql.expression import nullslast

from app import db
from util import clean_doi
from util import safe_commit

def get_gs_cache(dirty_doi):
    my_doi = clean_doi(dirty_doi)

    # return the best one we've got, so null urls are last
    my_gs = Gs.query.filter(Gs.doi==my_doi).order_by(Gs.landing_page_url.desc().nullslast()).first()

    if my_gs:
        my_gs.num_hits +=1
        safe_commit(db)
    return my_gs


def post_gs_cache(**kwargs):
    my_doi = clean_doi(kwargs["doi"])
    q = Gs.query.filter(Gs.doi==my_doi, Gs.landing_page_url==kwargs["landing_page_url"])
    my_gs = q.first()
    if not my_gs:
        my_gs = Gs(**kwargs)
        db.session.add(my_gs)
        safe_commit(db)
    return my_gs


class Gs(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text)
    landing_page_url = db.Column(db.Text)
    fulltext_url = db.Column(db.Text)
    created = db.Column(db.DateTime)
    num_hits = db.Column(db.Numeric, default=0)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow()
        if "doi" in kwargs:
            kwargs["doi"] = clean_doi(kwargs["doi"])
        super(Gs, self).__init__(**kwargs)

    def __repr__(self):
        return u"<GS ({}) {} {}>".format(self.id, self.doi, self.fulltext_url)

    def to_dict(self):
        response = {
            "doi": self.doi,
            "landing_page_url": self.landing_page_url,
            "fulltext_url": self.fulltext_url,
        }
        return response
