import json

from app import db


class WunpaywallPub(db.Model):
    __tablename__ = 'unpaywall_from_walden'
    __table_args__ = {'schema': 'unpaywall'}
    __bind_key__ = 'openalex'

    doi = db.Column(db.String, primary_key=True)
    json_response = db.Column(db.Text)

    def to_dict(self):
        response = json.loads(self.json_response)

        sorted_response = {
            "doi": response.get("doi"),
            "doi_url": response.get("doi_url"),
            "title": response.get("title"),
            "genre": response.get("genre"),
            "is_paratext": response.get("is_paratext"),
            "published_date": response.get("published_date"),
            "year": response.get("year"),
            "journal_name": response.get("journal_name"),
            "journal_issns": response.get("journal_issns"),
            "journal_issn_l": response.get("journal_issn_l"),
            "journal_is_oa": response.get("journal_is_oa"),
            "journal_is_in_doaj": response.get("journal_is_in_doaj"),
            "publisher": response.get("publisher"),
            "is_oa": response.get("is_oa"),
            "oa_status": response.get("oa_status"),
            "has_repository_copy": response.get("has_repository_copy"),
            "best_oa_location": response.get("best_oa_location"),
            "first_oa_location": response.get("first_oa_location"),
            "oa_locations": response.get("oa_locations"),
            "oa_locations_embargoed": response.get("oa_locations_embargoed"),
            "updated": response.get("updated"),
            "data_standard": response.get("data_standard"),
            "z_authors": response.get("z_authors")
        }
        return sorted_response
