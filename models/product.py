from app import db


def make_products_from_orcid_api_raw(orcid_api_raw):
    pass

def make_product(product_dict):
    pass

class Product(db.Model):
    id = db.Column(db.Text, primary_key=True)
    doi = db.Column(db.Text)
    api_raw = db.Column(db.Text)
    orcid = db.Column(db.Text, db.ForeignKey('profile.id'))

    title = db.Column(db.Text)
    year = db.Column(db.Text)

    @property
    def display_title(self):
        if self.title:
            return self.title
        else:
            return "No title"

    def __repr__(self):
        return u'<Product ({id}) "{title}" >'.format(
            id=self.id,
            title=self.display_title
        )




