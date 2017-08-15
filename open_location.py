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

    if "oa journal" in my_location.evidence:
        return -10

    if "publisher" in my_location.evidence:
        return -9

    if "hybrid" in my_location.evidence:
        return -8

    if "oa repo" in my_location.evidence:
        score = url_sort_score(my_location.best_fulltext_url)

        # if it was via pmcid lookup, give it a little boost
        if "pmcid lookup" in my_location.evidence:
            score -= 0.5

        # if had a doi match, give it a little boost because more likely a perfect match (negative is good)
        if "doi" in my_location.evidence:
            score -= 0.5
        return score

    return 0



class OpenLocation(db.Model):
    id = db.Column(db.Text, primary_key=True)
    pub_id = db.Column(db.Text, db.ForeignKey('crossref.id'))
    doi = db.Column(db.Text)  # denormalized from Publication for ease of interpreting

    created = db.Column(db.DateTime)
    updated = db.Column(db.DateTime)

    pdf_url = db.Column(db.Text)
    metadata_url = db.Column(db.Text)
    license = db.Column(db.Text)
    evidence = db.Column(db.Text)
    error = db.Column(db.Text)

    def __init__(self, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.doi = ""
        self.match = {}
        self.base_id = None
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
    def best_fulltext_url(self):
        if self.pdf_url:
            return self.pdf_url
        return self.metadata_url

    @property
    def base_collection(self):
        if not self.base_id:
            return None
        return self.base_id.split(":")[0]

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
    def is_pmc(self):
        if not self.best_fulltext_url:
            return False
        return "ncbi.nlm.nih.gov/pmc" in self.best_fulltext_url

    @property
    def pmcid(self):
        if not self.is_pmc:
            return None
        return self.best_fulltext_url.rsplit("/", 1)[1].lower()

    @property
    def is_pmc_author_manuscript(self):
        if not self.is_pmc:
            return False
        q = u"""select author_manuscript from pmcid_lookup where pmcid = '{}'""".format(self.pmcid)
        row = db.engine.execute(sql.text(q)).first()
        if not row:
            return False
        return row[0] == True

    @property
    def is_preprint_repo(self):
        preprint_url_fragments = [
            "precedings.nature.com",
            "arxiv.org/",
            "10.15200/winn.",
            "/peerj.preprints",
            ".figshare.",
            "10.1101/",  #biorxiv
            "10.15363/" #thinklab
        ]
        for url_fragment in preprint_url_fragments:
            if self.metadata_url and url_fragment in self.metadata_url.lower():
                return True
        return False

    @property
    def is_reported_noncompliant(self):
        if is_reported_noncompliant_url(self.doi, self.pdf_url) or is_reported_noncompliant_url(self.doi, self.metadata_url):
            return True
        return False

    @property
    def is_gold(self):
        if self.evidence and "oa journal" in self.evidence:
            return True
        return False


    @property
    def host_type(self):
        if self.is_gold or self.is_hybrid:
            return "publisher"
        return "repository"

    @property
    def is_doaj_journal(self):
        return "doaj" in self.evidence

    @property
    def is_hybrid(self):
        # import pdb; pdb.set_trace()

        if self.evidence and u"hybrid" in self.evidence:
            return True
        if self.is_publisher_base_collection:
            return True

        if is_doi_url(self.best_fulltext_url):
            if self.is_gold:
                return False
            if clean_doi(self.best_fulltext_url) == self.doi:
                return True
        return False


    @property
    def oa_color(self):
        if self.is_gold:
            return "gold"
        if self.is_hybrid:
            return "blue"
        if self.evidence=="closed" or not self.best_fulltext_url:
            return "gray"
        if not self.evidence:
            logger.info(u"should have evidence for {} but none".format(self.id))
            return None
        return "green"


    # use stanards from https://wiki.surfnet.nl/display/DRIVERguidelines/Version+vocabulary
    # submittedVersion, acceptedVersion, publishedVersion
    def find_version(self):
        if self.host_type == "publisher":
            return "publishedVersion"
        if self.is_preprint_repo:
            return "submittedVersion"
        if self.is_pmc:
            if self.is_pmc_author_manuscript:
                return "acceptedVersion"
            else:
                return "publishedVersion"

        if self.pdf_url:
            try:
                text = convert_pdf_to_txt(self.pdf_url)
                # logger.info(text)
                if text:
                    patterns = [
                        re.compile(ur"©.?\d{4}", re.UNICODE),
                        re.compile(ur"copyright \d{4}", re.IGNORECASE),
                        re.compile(ur"all rights reserved", re.IGNORECASE),
                        re.compile(ur"This article is distributed under the terms of the Creative Commons", re.IGNORECASE),
                        re.compile(ur"this is an open access article", re.IGNORECASE)
                        ]
                    for pattern in patterns:
                        matches = pattern.findall(text)
                        if matches:
                            return "publishedVersion"
            except Exception as e:
                self.error += u"Exception doing convert_pdf_to_txt on {}! investigate! {}".format(self.pdf_url, unicode(e.message).encode("utf-8"))
                logger.info(self.error)
                pass

        return "submittedVersion"

    @property
    def display_version(self):
        # return the scraped version if we have it
        if self.version:
            return self.version

        if self.host_type == "publisher":
            return "publishedVersion"
        if self.is_preprint_repo:
            return "submittedVersion"
        if self.is_pmc:
            if self.is_pmc_author_manuscript:
                return "acceptedVersion"
            else:
                return "publishedVersion"
        return "submittedVersion"



    def __repr__(self):
        return u"<OpenLocation ({}) {} {} {} {}>".format(self.id, self.doi, self.evidence, self.pdf_url, self.metadata_url)

    def to_dict(self):
        response = {
            # "_doi": self.doi,
            "pdf_url": self.pdf_url,
            "metadata_url": self.metadata_url,
            "license": self.license,
            "evidence": self.evidence,
            "base_id": self.base_id,
            "base_collection": self.base_collection,
            "oa_color": self.oa_color,
            "version": self.version
            # "base_doc": self.base_doc
        }

        if self.is_reported_noncompliant:
            response["reported_noncompliant"] = True

        return response

    def to_dict_v2(self, is_best):
        response = {
            "doi": self.doi,
            "updated": self.updated,
            "url": self.best_fulltext_url,
            "evidence": self.evidence,
            "license": self.license,
            "version": self.display_version,
            "host_type": self.host_type,
            "is_doaj_journal": self.is_doaj_journal,
            "is_best": is_best
        }

        if self.is_reported_noncompliant:
            response["reported_noncompliant"] = True

        return response
