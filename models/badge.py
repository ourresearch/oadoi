
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db

import datetime
import shortuuid


class BadgeRareness(db.Model):
    __table__ = db.Table(
        "badge_rareness",
        db.metadata,
        db.Column("name", db.Text, db.ForeignKey("badge.name"), primary_key=True),
        db.Column("percent_of_people", db.Float),
        autoload=True,
        autoload_with=db.engine
    )



class Badge(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)
    support = db.Column(db.Text)
    products = db.Column(MutableDict.as_mutable(JSONB))
    rareness_row = db.relationship(
        'BadgeRareness',
        lazy='subquery',
        foreign_keys="BadgeRareness.name"
    )

    def __init__(self, assigned=True, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        self.assigned = assigned
        self.products = {}
        super(Badge, self).__init__(**kwargs)

    @property
    def rareness(self):
        if self.rareness_row:
            return self.rareness_row[0].percent_of_people
        else:
            return 0


    @property
    def dois(self):
        if self.products:
            return self.products.keys()
        return []

    @property
    def num_products(self):
        if self.products:
            return len(self.products)
        else:
            return 0

    def add_products(self, products_list):
        for my_product in products_list:
            self.products[my_product.doi] = True


    def assign_from_badge_def(self, **badge_def):
        for k, v in badge_def.iteritems():
            setattr(self, k, v)

    def __repr__(self):
        return u'<Badge ({id} {name})>'.format(
            id=self.id,
            name=self.name
        )

    def to_dict(self):
        if self.products:
            product_list = self.products.keys()

        return {
            "id": self.id,
            "name": self.name,
            "created": self.created.isoformat(),
            "num_products": self.num_products,
            "rareness": self.rareness,
            "support": self.support,
            "dois": self.dois
        }