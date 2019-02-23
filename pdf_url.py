from app import db


class PdfUrl(db.Model):
    url = db.Column(db.Text, primary_key=True)
    publisher = db.Column(db.Text)
    is_pdf = db.Column(db.Boolean)
    http_status = db.Column(db.SmallInteger)
    last_checked = db.Column(db.DateTime)

    def __repr__(self):
        return u'<PdfUrl {}, {}, {}, {}, {}>'.format(
            self.url, self.publisher, self.is_pdf, self.http_status, self.last_checked)
