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
        score += -50

    # arxiv results are better than IR results, if we've got them
    if "arxiv" in url_lower:
        score += -40

    if ".edu" in url_lower:
        score += -30

    if "citeseerx" in url_lower:
        score += +10

    # ftp is really bad
    if "ftp" in url_lower:
        score += +60

    # break ties
    if "pdf" in url_lower:
        score += 1

    # otherwise whatever we've got
    return score






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
        if self.best_url and re.findall(u"ncbi.nlm.nih.gov/pmc", self.best_url):
           return True
        return False


    def set_pmc_version(self):
        if not self.is_pmc:
            return

        pmcid_matches = re.findall(".*(PMC\d+).*", self.best_url, re.IGNORECASE)
        if pmcid_matches:
            pmcid = pmcid_matches[0]

        pmcid_published_version = PmcidPublishedVersionLookup.query.get(pmcid.lower())

        if pmcid_published_version:
            self.version = "publishedVersion"
        else:
            self.version = "acceptedVersion"

    @property
    def sort_score(self):

        score = 0


        if self.host_type=="publisher":
            score += -1000

        if self.version=="publishedVersion":
            score += -600
        elif self.version=="acceptedVersion":
            score += -400
        elif self.version=="submittedVersion":
            score += -200
        # otherwise maybe version is null.  sort that to the bottom

        # this is very important
        if self.pdf_url:
            score += -100

        # if had a doi match, give it a little boost because more likely a perfect match (negative is good)
        if "doi" in self.display_evidence:
            score += -10

        # if pmcid lookup, give little boost, more likely correct
        if "via pmcid lookup" in self.display_evidence:
            score += -10

        # let the repos sort themselves out
        score += url_sort_score(self.best_url)

        return score


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
            "id": self.pmh_id,
            # "sort_score": self.sort_score
        }

        if self.is_reported_noncompliant:
            response["reported_noncompliant"] = True

        return response
