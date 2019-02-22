from app import db


class PdfUrlStatus(db.Model):
    url = db.Column(db.Text, primary_key=True)
    is_pdf = db.Column(db.Boolean)
    http_status = db.Column(db.SmallInteger)
    last_checked = db.Column(db.DateTime)

    def __repr__(self):
        return '<PdfUrlStatus {}, {}, {}>'.format(self.url, self.is_pdf, self.http_status, self.last_checked)