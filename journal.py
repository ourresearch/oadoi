from sqlalchemy.dialects.postgresql import JSONB

from app import db
from urllib import quote


class Journal(db.Model):
    issn_l = db.Column(db.Text, primary_key=True)
    issns = db.Column(JSONB)
    title = db.Column(db.Text)
    publisher = db.Column(db.Text)
    api_raw_crossref = db.Column(JSONB)
    api_raw_issn = db.Column(JSONB)

    @property
    def home_page(self):
        query = quote(u'{} {}'.format(self.title, self.issn_l).encode('utf-8'))
        url = u'https://www.google.com/search?q={}'.format(query)
        return url

    def to_csv_row(self):
        row = []
        for attr in ["home_page", "publisher", "title"]:
            value = getattr(self, attr) or u''
            value = value.replace(u',', u'; ')
            row.append(value)
        csv_row = u','.join(row)
        return csv_row

    def to_dict(self):
        return {
            "home_page": self.home_page,
            "institution_name": self.publisher,
            "repository_name": self.title
        }

    def __repr__(self):
        return u'<Journal ({issn_l})>'.format(
            issn_l=self.issn_l
        )