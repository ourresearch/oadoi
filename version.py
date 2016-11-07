import shortuuid

from app import db

def version_sort_score(my_version):
    # hybrid is best
    if "oa journal" in my_version.source:
        return 10

    if "oa repo" in my_version.source:
        return 8

    if "publisher" in my_version.source:
        return 6

    return 0



class Version(db.Model):
    id = db.Column(db.Text, primary_key=True)
    pub_id = db.Column(db.Text, db.ForeignKey('publication.id'))

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    free_pdf_url = db.Column(db.Text)
    free_pdf_medata_url = db.Column(db.Text)
    license = db.Column(db.Text)
    source = db.Column(db.Text)

    error = db.Column(db.Text)
    error_message = db.Column(db.Text)


    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        super(Version, self).__init__(**kwargs)

    def __repr__(self):
        return u"<Version ({}) {} {}>".format(self.id, self.publication.doi, self.free_pdf_url)

    def to_dict(self):
        response = {
            # "_title": self.best_title,
            "id": self.id,
            "free_pdf_url": self.free_pdf_url,
            "free_pdf_medata_url": self.free_pdf_medata_url,
            "license": self.license,
            "source": self.source
        }
        return response
