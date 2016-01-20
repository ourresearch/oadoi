from app import db

class NoDoiException(Exception):
    pass

def make_product(product_dict):
    product = Product()

    # get the DOI
    doi = None
    if product_dict.get('work-external-identifiers', []):
        for x in product_dict.get('work-external-identifiers', []):
            for eid in product_dict['work-external-identifiers']['work-external-identifier']:
                if eid['work-external-identifier-type'] == 'DOI':
                    doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()
    
    # AIP journals tend to have a \n in the DOI, and the doi is the second line. we get
    # that here.
    if len(doi.split('\n')) == 2:
        doi = doi.split('\n')[1]

    if doi:
        product.doi = doi
    else:
        raise NoDoiException("all products need a DOI.")

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

    return product

def dedup_products(products_list):

    # # Try to minimize duplicate entries that are found
    # dup = False
    # if (title and title.lower() in titles):
    #     dup = True
    # if (doi and doi in dois):
    #     dup = True

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

    def to_dict(self):
        return {
            "id": self.id,
            "doi": self.doi,
            "orcid": self.orcid,
            "title": self.title,
            "year": self.year
        }





