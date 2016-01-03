from sqlalchemy.dialects.postgresql import JSONB

from app import db
from models import provider

import os
import requests



def add_article(doi):
    my_article = Article(doi=doi)
    db.session.merge(my_article)
    db.session.commit()  
    return my_article


class Article(db.Model):
    doi = db.Column(db.Text, primary_key=True)
    title = db.Column(db.Text)
    author_string = db.Column(db.Text)
    journal = db.Column(db.Text)
    year = db.Column(db.Integer)
    abstract = db.Column(db.Text)

    def __repr__(self):
        return u'<Article ({doi}) "{title}" >'.format(
            doi=self.doi,
            title=self.title
        )

    def altmetric_metrics(self):
        print "HERE IS MY DOI"

        template = "http://api.altmetric.com/v1/doi/{doi}"
        url = template.format(doi=self.doi)
        print url
        resp = requests.get(url)

        if resp.status_code == 404:
            return {}

        return resp.json()


    def plos_metrics(self):
        template = "http://alm.plos.org/api/v3/articles?ids={doi_list}&source=citations,counter&api_key=" + os.environ["PLOS_KEY_V3"]
        url = template.format(doi_list=self.doi)
        resp = requests.get(url)

        if resp.status_code == 404:
            return {}
        if not "sources" in resp.text:
            return {}

        return resp.json()


    def crossref_deets(self):
        template = "http://doi.org/{doi}"
        url = template.format(doi=self.doi)
        headers={"Accept": "application/vnd.citationstyles.csl+json", "User-Agent": "impactstory.org"}
        resp = requests.get(url, headers=headers, allow_redirects=True)

        if resp.status_code == 404:
            return {}
        if not "DOI" in resp.text:
            return {}

        dict_of_keylists = {
            'title' : ['title'],
            'year' : ['issued'],
            'repository' : ['publisher'],
            'journal' : ['container-title']
            # 'authors_literal' : ['author']
        }
        biblio_dict = provider.extract_from_json(resp, dict_of_keylists)

        return biblio_dict

        if not biblio_dict:
          return {}


        try:
            surname_list = [author["family"] for author in biblio_dict["authors_literal"]]
            if surname_list:
                biblio_dict["authors"] = u", ".join(surname_list)
                del biblio_dict["authors_literal"]
        except (IndexError, KeyError):
            try:
                literal_list = [author["literal"] for author in biblio_dict["authors_literal"]]
                if literal_list:
                    biblio_dict["authors_literal"] = u"; ".join(literal_list)
            except (IndexError, KeyError):
                pass

        try:
            if "year" in biblio_dict:
                if "raw" in biblio_dict["year"]:
                    biblio_dict["year"] = str(biblio_dict["year"]["raw"])
                elif "date-parts" in biblio_dict["year"]:
                    biblio_dict["year"] = str(biblio_dict["year"]["date-parts"][0][0])
                biblio_dict["year"] = re.sub("\D", "", biblio_dict["year"])
                if not biblio_dict["year"]:
                    del biblio_dict["year"]

        except IndexError:
            logger.info(u"/biblio_print could not parse year {biblio_dict}".format(
                biblio_dict=biblio_dict))
            del biblio_dict["year"]

        # replace many white spaces and \n with just one space
        try:
            biblio_dict["title"] = re.sub(u"\s+", u" ", biblio_dict["title"])
        except KeyError:
            pass

        return biblio_dict  


