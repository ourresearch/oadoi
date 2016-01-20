from app import db
import json
import shortuuid

class NoDoiException(Exception):
    pass

def make_product(product_dict):
    product = Product(id=shortuuid.uuid()[0:10])

    # get the DOI
    doi = None
    if product_dict.get('work-external-identifiers', []):
        for x in product_dict.get('work-external-identifiers', []):
            for eid in product_dict['work-external-identifiers']['work-external-identifier']:
                if eid['work-external-identifier-type'] == 'DOI':
                    doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()

    if not doi:  # this should become actual validation check in the future.
        raise NoDoiException("all products need a DOI.")

    # AIP journals tend to have a \n in the DOI, and the doi is the second line.
    # we get that here. put this in the validation function later.
    if len(doi.split('\n')) == 2:
        doi = doi.split('\n')[1]

    product.doi = doi

    # get the title
    try:
        product.title = str(product_dict['work-title']['title']['value'].encode('utf-8'))
    except TypeError:
        product.title = None

    # get the publication date
    pub_date = product_dict.get('publication-date', None)
    if pub_date:
        product.year = pub_date.get('year', None).get('value').encode('utf-8')
    else:
        product.year = None

    product.api_raw = json.dumps(product_dict)

    return product



class Product(db.Model):
    id = db.Column(db.Text, primary_key=True)
    title = db.Column(db.Text)
    year = db.Column(db.Text)
    doi = db.Column(db.Text)
    api_raw = db.Column(db.Text)
    orcid = db.Column(db.Text, db.ForeignKey('profile.id'))


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

    def to_dict(self):
        return {
            "id": self.id,
            "doi": self.doi,
            "orcid": self.orcid,
            "title": self.title,
            "year": self.year
        }





