
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db

import datetime
import shortuuid


# badge_rareness_table = db.Table("badge_rareness",
#                 db.Column("name", db.Text, db.ForeignKey("badge.name"), primary_key=True),
#                 db.Column("percent_of_people", db.Float),
#                 autoload=True
# )


class Badge(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)
    products = db.Column(MutableDict.as_mutable(JSONB))

    # rareness = db.relationship(
    #     'Product',
    #     lazy='subquery',
    #     cascade="all, delete-orphan",
    #     backref=db.backref("person", lazy="subquery"),
    #     foreign_keys="Product.orcid_id"
    # )

    def __init__(self, assigned=True, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        self.assigned = assigned
        self.products = {}
        super(Badge, self).__init__(**kwargs)

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
            "dois": self.dois
        }