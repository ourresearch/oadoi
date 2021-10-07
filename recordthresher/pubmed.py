from app import db


class PubmedWork(db.Model):
    __tablename__ = 'pubmed_works'
    __table_args__ = {'schema': 'recordthresher'}

    pmid = db.Column(db.Text, primary_key=True)
    created = db.Column(db.DateTime)
    doi = db.Column(db.Text)
    pmcid = db.Column(db.Text)
    year = db.Column(db.Text)
    issn = db.Column(db.Text)
    article_title = db.Column(db.Text)
    abstract = db.Column(db.Text)
    pubmed_article_xml = db.Column(db.Text)


class PubmedAuthor(db.Model):
    __tablename__ = 'pubmed_author'
    __table_args__ = {'schema': 'recordthresher'}

    pmid = db.Column(db.Text, primary_key=True)
    author_order = db.Column(db.Integer, primary_key=True)
    doi = db.Column(db.Text)
    created = db.Column(db.DateTime)
    family = db.Column(db.Text)
    given = db.Column(db.Text)
    initials = db.Column(db.Text)
    orcid = db.Column(db.Text)


class PubmedReference(db.Model):
    __tablename__ = 'pubmed_reference'
    __table_args__ = {'schema': 'recordthresher'}

    pmid = db.Column(db.Text, primary_key=True)
    reference_number = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime)
    doi = db.Column(db.Text)
    reference = db.Column(db.Text)
    pmid_referenced = db.Column(db.Text)
    citation = db.Column(db.Text)


class PubmedAffiliation(db.Model):
    __tablename__ = 'pubmed_affiliation'
    __table_args__ = {'schema': 'recordthresher'}

    pmid = db.Column(db.Text, primary_key=True)
    author_order = db.Column(db.Integer, primary_key=True)
    affiliation_number = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime)
    affiliation = db.Column(db.Text)


class PubmedRaw(db.Model):
    __tablename__ = 'pubmed_raw'
    __table_args__ = {'schema': 'recordthresher'}

    pmid = db.Column(db.Text, primary_key=True)
    created = db.Column(db.DateTime)
    doi = db.Column(db.Text)
    pmcid = db.Column(db.Text)
    pubmed_article_xml = db.Column(db.Text)


class PubmedArticleType(db.Model):
    __tablename__ = 'pubmed_article_type'
    __table_args__ = {'schema': 'recordthresher'}

    article_type = db.Column(db.Text, primary_key=True)
    relative_frequency = db.Column(db.Float)
    rank = db.Column(db.Integer)
