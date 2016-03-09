
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db

import datetime
import shortuuid



class Badge(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)
    products = db.Column(MutableDict.as_mutable(JSONB))


    def __init__(self, **kwargs):
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