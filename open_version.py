import shortuuid

from app import db

def version_sort_score(my_version):

    if "oa journal" in my_version.source:
        return 10

    if "oa repo" in my_version.source:
        return 8

    if "publisher" in my_version.source:
        return 6

    return 0



class OpenVersion(db.Model):
    id = db.Column(db.Text, primary_key=True)
    pub_id = db.Column(db.Text, db.ForeignKey('publication.id'))
    doi = db.Column(db.DateTime)  # denormalized from Publication for ease of interpreting

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    pdf_url = db.Column(db.Text)
    metadata_url = db.Column(db.Text)
    license = db.Column(db.Text)
    source = db.Column(db.Text)

    error = db.Column(db.Text)
    error_message = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        super(OpenVersion, self).__init__(**kwargs)

    def __repr__(self):
        return u"<OpenVersion ({}) {} {}>".format(self.id, self.publication.doi, self.pdf_url)

    def to_dict(self):
        response = {
            # "_doi": self.doi,
            "pdf_url": self.pdf_url,
            "metadata_url": self.metadata_url,
            "license": self.license,
            "source": self.source
        }
        return response
