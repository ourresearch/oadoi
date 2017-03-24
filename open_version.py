import shortuuid

from app import db


def url_sort_score(url):
    # pmc results are better than IR results, if we've got them
    if "/pmc/" in url:
        return -5

    # arxiv results are better than IR results, if we've got them
    if "arxiv" in url:
        return -4

    # pubmed results not as good as pmc results
    if "/pubmed/" in url:
        return -3

    if ".edu" in url:
        return -2

    # sometimes the base doi isn't actually open, like in this record:
    # https://www.base-search.net/Record/9b574f9768c8c25d9ed6dd796191df38a865f870fde492ee49138c6100e31301/
    # so sort doi down in the list
    if "doi.org" in url:
        return -1

    if "citeseerx" in url:
        return +9

    # otherwise whatever we've got
    return 0



def version_sort_score(my_version):

    if "oa journal" in my_version.source:
        return -10

    if "publisher" in my_version.source:
        return -9

    if "hybrid" in my_version.source:
        return -8

    if "oa repo" in my_version.source:
        score = url_sort_score(my_version.best_fulltext_url)
        # if had a doi match, give it a little boost because more likely a perfect match (negative is good)
        if "doi" in my_version.source:
            score -= 0.5
        return score

    return 0



class OpenVersion(db.Model):
    id = db.Column(db.Text, primary_key=True)
    pub_id = db.Column(db.Text, db.ForeignKey('publication.id'))
    doi = db.Column(db.Text)  # denormalized from Publication for ease of interpreting

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
        self.doi = ""
        self.match = {}
        self.base_id = None
        super(OpenVersion, self).__init__(**kwargs)

    @property
    def best_fulltext_url(self):
        if self.pdf_url:
            return self.pdf_url
        return self.metadata_url


    def __repr__(self):
        return u"<OpenVersion ({}) {} {}>".format(self.id, self.doi, self.pdf_url)

    def to_dict(self):
        response = {
            # "_doi": self.doi,
            "pdf_url": self.pdf_url,
            "metadata_url": self.metadata_url,
            "license": self.license,
            "source": self.source
        }
        return response
