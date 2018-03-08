import shortuuid

from app import db

class Abstract(db.Model):
    doi = db.Column(db.Text, db.ForeignKey('pub.id'), primary_key=True)
    source = db.Column(db.Text)
    source_id = db.Column(db.Text, primary_key=True)
    abstract = db.Column(db.Text)

    def to_dict(self):
        response = {
            "source": self.source,
            "source_id": self.source_id,
            "abstract": self.abstract
        }
        return response