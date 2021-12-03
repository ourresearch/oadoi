# -*- coding: utf8 -*-
#

import re
from enum import Enum
from urllib.parse import unquote

import shortuuid

import oa_evidence
from app import db
from app import logger
from pdf_url import PdfUrl
from reported_noncompliant_copies import is_reported_noncompliant_url
from util import is_doi_url
from util import normalize_doi


def url_sort_score(url):
    url_lower = url.lower()

    score = 0

    # pmc results are better than IR results, if we've got them
    if "europepmc.org" in url_lower:
        score += -50

    if "/pmc/" in url_lower:
        score += -45

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
        score += -1

    # otherwise whatever we've got
    return score


def validate_pdf_urls(open_locations):
    unvalidated = [x for x in open_locations if x.pdf_url_valid is None]

    if unvalidated:
        bad_pdf_urls = {
            x.url for x in
            PdfUrl.query.filter(
                PdfUrl.url.in_([x.pdf_url for x in unvalidated]),
                PdfUrl.is_pdf.is_(False)
            ).all()
        }

        for location in unvalidated:
            location.pdf_url_valid = (
                location.pdf_url not in bad_pdf_urls
                # get rid of this, make PDF checker more robust
                or 'journal.csj.jp/doi/pdf' in location.pdf_url
            )

            if not location.pdf_url_valid:
                logger.info('excluding location with bad pdf url: {}'.format(location))


class OAStatus(Enum):
    closed = 'closed'
    green = 'green'
    bronze = 'bronze'
    hybrid = 'hybrid'
    gold = 'gold'


def oa_status_sort_key(location):
    keys = {
        OAStatus.closed:    0,
        OAStatus.green:     1,
        OAStatus.bronze:    2,
        OAStatus.hybrid:    3,
        OAStatus.gold:      4,
    }

    return keys.get(location.oa_status, 0)


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
        self.id = shortuuid.uuid()[0:20]
        self.doi = ""
        self.match = {}
        self.pmh_id = None
        self.endpoint_id = None
        self.base_doc = None
        self.version = None
        self.error = ""
        self.pdf_url_valid = None
        self.institution = None
        self.oa_date = None
        self.publisher_specific_license = None
        super(OpenLocation, self).__init__(**kwargs)

    @property
    def has_open_license(self):
        if not self.license:
            return False
        if self.license in (
            "unknown",
            "elsevier-specific: oa user license",
        ) or self.publisher_specific_license in (
            "http://onlinelibrary.wiley.com/termsAndConditions#am",
            "http://www.apa.org/pubs/journals/resources/open-access.aspx",
        ):
            return False
        return True

    @property
    def best_url(self):
        return self.pdf_url or self.metadata_url

    @property
    def best_url_is_pdf(self):
        if not self.best_url:
            return None
        if self.pdf_url:
            return True
        return False

    @property
    def is_reported_noncompliant(self):
        if is_reported_noncompliant_url(self.doi, self.pdf_url) or is_reported_noncompliant_url(self.doi, self.metadata_url):
            return True
        return False

    @property
    def is_gold(self):
        return self.best_url and self.display_evidence.startswith(oa_evidence.oa_journal_prefix)

    @property
    def is_green(self):
        return self.best_url and self.display_evidence.startswith('oa repository')

    @property
    def is_hybrid(self):
        return self.best_url and not (self.is_gold or self.is_green) and self.has_open_license

    @property
    def is_bronze(self):
        if self.best_url and not (self.is_gold or self.is_green) and not self.has_open_license:
            return True

        if is_doi_url(self.best_url):
            url_doi = normalize_doi(self.best_url, return_none_if_error=True)
            unquoted_doi = normalize_doi(unquote(self.best_url), return_none_if_error=True)

            return (
                self.doi in (url_doi, unquoted_doi)
                and not (self.is_gold or self.is_hybrid or self.is_green)
            )

        return False

    @property
    def display_evidence(self):
        return self.evidence or ''

    @property
    def host_type_calculated(self):
        if self.is_gold or self.is_hybrid or self.is_bronze:
            return "publisher"
        return "repository"

    @property
    def host_type(self):
        if hasattr(self, "host_type_set"):
            return self.host_type_set
        else:
            return self.host_type_calculated

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
    def oa_status(self):
        if self.is_gold:
            return OAStatus.gold
        if self.is_hybrid:
            return OAStatus.hybrid
        if self.is_bronze:
            return OAStatus.bronze
        if self.is_green:
            return OAStatus.green
        if not self.best_url:
            return OAStatus.closed
        if not self.display_evidence:
            logger.info("should have evidence for {} but none".format(self.id))

        return OAStatus.green

    @property
    def is_pmc(self):
        if self.best_url and re.findall("ncbi.nlm.nih.gov/pmc", self.best_url):
            return True
        return False

    @property
    def sort_score(self):

        score = 0

        if self.host_type == "publisher":
            score += -1000
            if self.display_evidence in [oa_evidence.oa_journal_manual, oa_evidence.oa_journal_observed]:
                score += 100
            if self.has_open_license:
                # give gold/hybrid locations a boost so they aren't removed by deduplication
                score += -50
        else:
            # doi.org urls for preprints are called repositories. prefer them over other repos.
            if self.doi and self.metadata_url and self.doi in self.metadata_url:
                score += -50

        if self.version == "publishedVersion":
            score += -600
            if self.metadata_url == "https://doi.org/{}".format(self.doi):
                score += -200
        elif self.version == "acceptedVersion":
            score += -400
        elif self.version == "submittedVersion":
            score += -200
        # otherwise maybe version is null.  sort that to the bottom

        # this is very important
        if self.pdf_url:
            score += -100

        # if had a doi match, give it a little boost because more likely a perfect match (negative is good)
        if "doi" in self.display_evidence:
            score += -10

        # penalize versioned preprint dois like 10.26434/chemrxiv.12073869.v1 to let 10.26434/chemrxiv.12073869 win
        if self.host_type == 'repository' and self.metadata_url and re.findall(r'\.v\d+$', self.metadata_url):
            score += 5

        # let the repos sort themselves out
        score += url_sort_score(self.best_url)

        return score

    def __repr__(self):
        return "<OpenLocation ({}) {} {} {} {}>".format(self.id, self.doi, self.display_evidence, self.pdf_url, self.metadata_url)

    def to_dict(self):
        response = {
            "pdf_url": self.pdf_url,
            "metadata_url": self.metadata_url,
            "license": self.license,
            "evidence": self.display_evidence,
            "pmh_id": self.pmh_id,
            "endpoint_id": self.endpoint_id,
            "oa_color": self.oa_status.value,
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
            "pmh_id": self.pmh_id,
            "endpoint_id": self.endpoint_id,
            "repository_institution": self.institution,
            "oa_date": self.oa_date and self.oa_date.isoformat(),
        }

        if self.is_reported_noncompliant:
            response["reported_noncompliant"] = True

        return response
