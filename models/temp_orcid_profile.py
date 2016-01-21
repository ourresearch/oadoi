from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import deferred

from app import db
from models import provider

import os
import requests
import json
import datetime


def add_orcid_profile(**kwargs):
    my_profile = TempOrcidProfile(**kwargs)
    db.session.merge(my_profile)
    db.session.commit()  
    return my_profile


class TempOrcidProfile(db.Model):
    id = db.Column(db.Text, primary_key=True)
    given_names = db.Column(db.Text)
    family_name = db.Column(db.Text)
    created = db.Column(db.DateTime())
    modified = db.Column(db.DateTime())
    created_method = db.Column(db.Text)
    num_works = db.Column(db.Integer)
    num_all_dois = db.Column(db.Integer)
    num_dois_since_2010 = db.Column(db.Integer)
    api_raw = deferred(db.Column(db.Text))

    update_marker = db.Column(db.DateTime())
    
    twitter = db.Column(db.Text)
    researcher_urls = db.Column(db.Integer)
    public_email = db.Column(db.Text)
    institution = db.Column(db.Text)
    has_bio = db.Column(db.Boolean)
    dois = db.Column(db.Text)
    num_2015_dois = db.Column(db.Integer)
    last_doi_created = db.Column(db.DateTime())    


    products = db.relationship(
        'TempProduct',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("temp_orcid_profile", lazy="subquery")
    )




    def get_researcher_urls(self, profile_json):
        try:
            url_dicts = profile_json["orcid-bio"]["researcher-urls"]["researcher-url"]
        except (KeyError, TypeError):
            url_dicts = []
        return url_dicts

    def set_twitter(self, profile_json):
        for url_dict in self.get_researcher_urls(profile_json):
            if "twitter.com" in url_dict["url"]["value"]:
                self.twitter = url_dict["url"]["value"]
                print "**************added twitter", self.twitter


    def set_researcher_urls(self, profile_json):
        urls = self.get_researcher_urls(profile_json)
        if urls:
            self.researcher_urls = len(urls)
        else:
            self.researcher_urls = 0


    def set_public_email(self, profile_json):
        try:
            self.public_email = profile_json["orcid-bio"]["contact-details"]["email"][0]["value"]
            print "**************added email", self.public_email
        except (TypeError, KeyError, IndexError):
            pass


    def set_has_bio(self, profile_json):
        self.has_bio = False
        try:
            if profile_json["orcid-bio"]["biography"]["value"]:
                self.has_bio = True
        except (TypeError, KeyError):
            pass

    def set_dois(self, profile_json):
        (dois, dois_since_2015, max_created_date) = self.get_works(profile_json)
        self.dois = dois

    def set_num_2015_dois(self, profile_json):
        (dois, dois_since_2015, max_created_date) = self.get_works(profile_json)
        self.num_2015_dois = len(dois_since_2015)

    def set_last_doi_created(self, profile_json):
        (dois, dois_since_2015, max_created_date) = self.get_works(profile_json)
        self.last_doi_created = max_created_date


    def get_works(self, profile_json):
        works = profile_json["orcid-activities"]["orcid-works"]["orcid-work"]
        dois = []
        dois_since_2015 = []
        max_created_date = '0'

        if works:

            for i, result in enumerate(works):

                try:
                    title = str(result['work-title']['title']['value'].encode('utf-8'))
                except TypeError:
                    title = ""
                doi = ""

                if result.get('work-external-identifiers', []):
                    for x in result.get('work-external-identifiers', []):
                        for eid in result['work-external-identifiers']['work-external-identifier']:
                            if eid['work-external-identifier-type'] == 'DOI':
                                doi = str(eid['work-external-identifier-id']['value'].encode('utf-8')).lower()

                # AIP journals tend to have a \n in the DOI, and the doi is the second line. we get
                # that here.
                if len(doi.split('\n')) == 2:
                    doi = doi.split('\n')[1]

                pub_date = result.get('publication-date', None)
                if pub_date:
                    year = pub_date.get('year', None).get('value').encode('utf-8')
                else:
                    year = 'Unknown'

                # Try to minimize duplicate entries that are found
                dup = False
                if (doi and doi in dois):
                    dup = True

                if not dup:
                    # truncate title to first 50 characters
                    print('| {3} | {0}  | {1} | [[doi:{2}]]|'.format(title[0:50], year, doi, result['work-type']))

                    if doi:
                        dois.append(doi)
                        if year and year != 'Unknown' and int(year) == 2015:
                            dois_since_2015.append(doi)

                        created_date = datetime.datetime.fromtimestamp(result["created-date"]["value"]/1000).isoformat()
                        if created_date > max_created_date:
                            max_created_date = created_date

        return (dois, dois_since_2015, max_created_date)



    def set_stuff(self):
        profile_json = json.loads(self.api_raw)

        self.set_twitter(profile_json)
        self.set_researcher_urls(profile_json)
        self.set_public_email(profile_json)
        self.set_has_bio(profile_json)
        # self.set_institution(profile_json)  # can't figure out how to get it for todd http://orcid.org/0000-0002-6133-2581/orcid-bio
        self.set_dois(profile_json)
        self.set_num_2015_dois(profile_json)
        self.set_last_doi_created(profile_json)


        self.update_marker = datetime.datetime.now().isoformat()


    def __repr__(self):
        return u'<TempOrcidProfile ({id}) "{given_names} {family_name}" >'.format(
            id=self.id,
            given_names=self.given_names, 
            family_name=self.family_name
        )




