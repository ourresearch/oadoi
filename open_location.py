# -*- coding: utf8 -*-
#

import shortuuid
import re
from sqlalchemy import sql

from app import db
from app import logger
from oa_pdf import convert_pdf_to_txt
from util import clean_doi
from util import is_doi_url
from reported_noncompliant_copies import is_reported_noncompliant_url

class PmcidPublishedVersionLookup(db.Model):
    pmcid = db.Column(db.Text, primary_key=True)


def url_sort_score(url):
    url_lower = url.lower()

    score = 0

    # pmc results are better than IR results, if we've got them
    if "/pmc/" in url_lower:
        score = -5

    # arxiv results are better than IR results, if we've got them
    elif "arxiv" in url_lower:
        score = -4

    # pubmed results not as good as pmc results
    elif "/pubmed/" in url_lower:
        score = -3

    elif ".edu" in url_lower:
        score = -2

    # sometimes the base doi isn't actually open, like in this record:
    # https://www.base-search.net/Record/9b574f9768c8c25d9ed6dd796191df38a865f870fde492ee49138c6100e31301/
    # so sort doi down in the list
    elif "doi.org" in url_lower:
        score = -1

    elif "citeseerx" in url_lower:
        score = +9

    # break ties
    elif "pdf" in url_lower:
        score -= 0.5

    # otherwise whatever we've got
    return score



def location_sort_score(my_location):

    if my_location.display_evidence and my_location.display_evidence.startswith("open"):
        return -10

    if "oa journal" in my_location.display_evidence:
        return -9

    if "publisher" in my_location.display_evidence:
        return -7

    if "oa repo" in my_location.display_evidence:
        score = url_sort_score(my_location.best_url)

        # if it was via pmcid lookup, give it a little boost
        if "pmcid lookup" in my_location.display_evidence:
            score -= 0.5

        # if had a doi match, give it a little boost because more likely a perfect match (negative is good)
        if "doi" in my_location.display_evidence:
            score -= 0.5

        # if oai-pmh give it a boost
        if "OAI-PMH" in my_location.display_evidence:
            score -= 0.5

        return score

    return 0



class OpenLocation(db.Model):
    id = db.Column(db.Text, primary_key=True)
    pub_id = db.Column(db.Text, db.ForeignKey('pub.id'))
    doi = db.Column(db.Text)  # denormalized from Publication for ease of interpreting

    pdf_url = db.Column(db.Text)
    metadata_url = db.Column(db.Text)
    license = db.Column(db.Text)
    evidence = db.Column(db.Text)
    updated = db.Column(db.DateTime)
    error = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.doi = ""
        self.match = {}
        self.pmh_id = None
        self.base_doc = None
        self.version = None
        self.error = ""
        super(OpenLocation, self).__init__(**kwargs)

    @property
    def has_license(self):
        if not self.license:
            return False
        if self.license == "unknown":
            return False
        return True

    @property
    def best_url(self):
        if self.pdf_url:
            return self.pdf_url
        return self.metadata_url

    @property
    def base_collection(self):
        if not self.pmh_id:
            return None
        return self.pmh_id.split(":")[0]

    @property
    def is_publisher_base_collection(self):
        publisher_base_collections = [
            "fthighwire",
            "ftdoajarticles",
            "crelsevierbv",
            "ftcopernicus",
            "ftdoajarticles"
        ]
        if not self.base_collection:
            return False
        return self.base_collection in publisher_base_collections

    @property
    def is_reported_noncompliant(self):
        if is_reported_noncompliant_url(self.doi, self.pdf_url) or is_reported_noncompliant_url(self.doi, self.metadata_url):
            return True
        return False

    @property
    def is_gold(self):
        if self.display_evidence and "oa journal" in self.display_evidence:
            return True
        return False

    @property
    def display_evidence(self):
        if self.evidence:
            return self.evidence.replace("hybrid", "open")
        return ""

    @property
    def host_type(self):
        if self.is_gold or self.is_hybrid:
            return "publisher"
        return "repository"

    @property
    def is_doaj_journal(self):
        return "doaj" in self.display_evidence

    @property
    def display_updated(self):
        if self.updated:
            try:
                return self.updated.isoformat()
            except AttributeError:
                return self.updated
        return None


    @property
    def is_hybrid(self):
        # import pdb; pdb.set_trace()

        if self.display_evidence and self.display_evidence.startswith("open"):
            return True
        if self.is_publisher_base_collection:
            return True

        if is_doi_url(self.best_url):
            if self.is_gold:
                return False
            if clean_doi(self.best_url) == self.doi:
                return True
        return False


    @property
    def oa_color(self):
        if self.is_gold:
            return "gold"
        if self.is_hybrid:
            return "bronze"
        if self.display_evidence=="closed" or not self.best_url:
            return "gray"
        if not self.display_evidence:
            logger.info(u"should have evidence for {} but none".format(self.id))
            return None
        return "green"

    @property
    def is_pmc(self):
        if self.scraped_pdf_url and re.match(u"ncbi.nlm.nih.gov/pmc", self.scraped_pdf_url):
           return True
        return False


    def set_pmc_version(self):
        if not self.is_pmc:
            return

        pmcid_matches = re.findall(".*(PMC\d+).*", self.scraped_pdf_url, re.IGNORECASE)
        if pmcid_matches:
            pmcid = pmcid_matches[0]

        pmcid_published_version = PmcidPublishedVersionLookup.query.get(pmcid)

        if pmcid_published_version:
            self.version = "publishedVersion"
        else:
            self.version = "acceptedVersion"


    def __repr__(self):
        return u"<OpenLocation ({}) {} {} {} {}>".format(self.id, self.doi, self.display_evidence, self.pdf_url, self.metadata_url)

    def to_dict(self):
        response = {
            "pdf_url": self.pdf_url,
            "metadata_url": self.metadata_url,
            "license": self.license,
            "evidence": self.display_evidence,
            "pmh_id": self.pmh_id,
            "base_collection": self.base_collection,
            "oa_color": self.oa_color,
            "version": self.version
        }

        if self.is_reported_noncompliant:
            response["reported_noncompliant"] = True

        return response

    def to_dict_v2(self):
        if hasattr(self, "is_best"):
            is_best = self.is_best
        else:
            is_best = False

        response = {
            "updated": self.display_updated,
            "url": self.best_url,
            "url_for_pdf": self.pdf_url,
            "url_for_landing_page": self.metadata_url,
            "evidence": self.display_evidence,
            "license": self.license,
            "version": self.version,
            "host_type": self.host_type,
            "is_best": is_best,
            "id": self.pmh_id
        }

        if self.is_reported_noncompliant:
            response["reported_noncompliant"] = True

        return response
