from app import db
from sqlalchemy.dialects.postgresql import JSONB

from util import dict_from_dir

# sqla needs these two imports when you get started:
#from models import package
#from models import person

class Contribution(db.Model):
    __tablename__ = 'contribution'

    id = db.Column(db.Integer, primary_key=True)

    person_id = db.Column(db.Integer, db.ForeignKey("person.id"))
    package_id = db.Column(db.Text, db.ForeignKey("package.id"))

    role = db.Column(db.Text)
    quantity = db.Column(db.Integer)
    percent = db.Column(db.Float)

    def __repr__(self):
        return u"Contribution from Person #{} to Package {}".format(
            self.person_id,
            self.package_id
        )

    def to_dict(self):
        ret = {
            "role": self.role,
            "quantity": self.quantity,
            "percent": self.get_percent(),
            "package": self.package.as_snippet,
            "person": self.person.to_dict(full=False),
            "fractional_sort_score": self.fractional_sort_score
        }
        return ret


    @property
    def as_snippet(self):
        return {
            "name": self.role,
            "quantity": self.quantity
        }

    @property
    def fractional_sort_score(self):
        if self.percent:
            fraction = self.percent / 100.0
        else:
            fraction = 1.0

        try:
            return self.package.impact * fraction
        except TypeError:  # no sort score for some reason?
            return 0
        except AttributeError:
            # no package, this is an orphan contribution
            return 0

    def get_percent(self):
        if self.percent is None:
            return 100
        else:
            return self.percent








