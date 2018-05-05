from sqlalchemy.dialects.postgresql import JSONB

from app import db

class Abstract(db.Model):
    doi = db.Column(db.Text, db.ForeignKey('pub.id'), primary_key=True)
    source = db.Column(db.Text)
    source_id = db.Column(db.Text, primary_key=True)
    abstract = db.Column(db.Text)
    mesh = db.Column(JSONB)
    keywords = db.Column(JSONB)

    def to_dict(self):
        response = {
            "source": self.source,
            "source_id": self.source_id,
            "abstract": self.abstract
        }
        if self.mesh:
            response["mesh_discriptor_names"] = [m["descriptorName"] for m in self.mesh]
        if self.keywords:
            response["keywords"] = self.keywords
        return response