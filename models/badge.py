
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db

import datetime
import shortuuid


def badge_configs_without_functions():
    from models import badge_defs
    resp = []
    for badge_def in badge_defs.all_badge_defs:
        badge_def.pop("function", None)
        resp.append(badge_def)
    return resp

class Badge(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)
    products = db.Column(MutableDict.as_mutable(JSONB))


    def __init__(self, **kwargs):
        shortuuid.set_alphabet('abcdefghijklmnopqrstuvwxyz1234567890')
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        super(Badge, self).__init__(**kwargs)

    @property
    def num_products(self):
        if self.products:
            return len(self.products)
        else:
            return 0

    def __repr__(self):
        return u'<Badge ({id} {name})>'.format(
            id=self.id,
            name=self.name
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "num_products": self.num_products,
            "products": self.products
        }