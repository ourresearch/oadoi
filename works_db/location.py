from app import db


class Location(db.Model):
    __tablename__ = 'location'
    __table_args__ = {'schema': 'works_db'}

    id = db.Column(db.Text, primary_key=True)
    location_type = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text)
    url = db.Column(db.Text)
    landing_page_content_url = db.Column(db.Text)
    fulltext_pdf_content_url = db.Column(db.Text)
    is_oa = db.Column(db.Boolean)
    oa_date = db.Column(db.DateTime)
    open_landing_url = db.Column(db.Text)
    open_pdf_url = db.Column(db.Text)
    open_license = db.Column(db.Text)
    open_version = db.Column(db.Text)

    external_ids = db.relationship('LocationExternalId', back_populates='location')

    def id_prefix(self):
        raise NotImplementedError()

    __mapper_args__ = {'polymorphic_on': location_type}

    def __repr__(self):
        return "<Location ( {} ) {}, {}>".format(self.id, self.location_type, self.external_ids)


class LocationExternalIdScheme(db.Model):
    __table_args__ = {'schema': 'works_db'}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    short_name = db.Column(db.Text, unique=True)
    name = db.Column(db.Text)

    def __repr__(self):
        return "<LocationExternalIdScheme ( {} ) {}, {}>".format(self.id, self.short_name, self.name)


class LocationExternalId(db.Model):
    __table_args__ = {'schema': 'works_db'}

    location_id = db.Column(db.Text, db.ForeignKey(Location.id), primary_key=True)
    scheme_id = db.Column(db.Integer, db.ForeignKey(LocationExternalIdScheme.id), primary_key=True)
    value = db.Column(db.Text, primary_key=True)

    scheme = db.relationship(LocationExternalIdScheme, uselist=False)
    location = db.relationship(Location, uselist=False, back_populates='external_ids')

    def __repr__(self):
        if self.scheme:
            scheme_repr = self.scheme.short_name
        else:
            scheme_repr = f'scheme_id {self.scheme_id}'

        return "<LocationExternalId ( {}, {}: {}>".format(self.location_id, scheme_repr, self.value)


