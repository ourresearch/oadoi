from sqlalchemy.dialects.postgresql import JSONB

from app import db
from urllib.parse import quote


class Journal(db.Model):
    issn_l = db.Column(db.Text, primary_key=True)
    issns = db.Column(JSONB)
    title = db.Column(db.Text)
    publisher = db.Column(db.Text)
    delayed_oa = db.Column(db.Boolean)
    embargo = db.Column(db.Interval)
    api_raw_crossref = db.Column(JSONB)
    api_raw_issn = db.Column(JSONB)
    url = db.Column(db.Text)

    @property
    def home_page(self):
        if self.url:
            return self.url
        else:
            query = quote('{} {}'.format(self.title, self.issn_l).encode('utf-8'))
            url = 'https://www.google.com/search?q={}'.format(query)
        return url

    def to_csv_row(self):
        row = []
        for attr in ["home_page", "publisher", "title"]:
            value = getattr(self, attr) or ''
            value = value.replace(',', '; ')
            row.append(value)
        csv_row = ','.join(row)
        return csv_row

    def to_dict(self):
        return {
            "home_page": self.home_page,
            "institution_name": self.publisher,
            "repository_name": self.title
        }

    def __repr__(self):
        return '<Journal ({issn_l}, {title})>'.format(
            issn_l=self.issn_l, title=self.title
        )
