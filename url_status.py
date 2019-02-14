from app import db


class URLStatus(db.Model):
    url = db.Column(db.Text, primary_key=True)
    is_ok = db.Column(db.Boolean)
    http_status = db.Column(db.SmallInteger)
    last_checked = db.Column(db.DateTime)

    def __repr__(self):
        return '<URLStatus {}, {}, {}>'.format(self.url, self.is_ok, self.http_status, self.last_checked)