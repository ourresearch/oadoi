#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import re
from HTMLParser import HTMLParser

from sqlalchemy import or_, orm
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app import logger
import page
from util import NoDoiException
from util import clean_doi
from util import is_doi_url
from util import normalize_title

DEBUG_BASE = False





def title_is_too_short(normalized_title):
    if not normalized_title:
        return True
    return len(normalized_title) <= 21

def title_is_too_common(normalized_title):
    # these common titles were determined using this SQL,
    # which lists the titles of BASE hits that matched titles of more than 2 articles in a sample of 100k articles.
    # ugly sql, i know.  but better to include here as a comment than not, right?
    #     select norm_title, count(*) as c from (
    #     select id, response_jsonb->>'free_fulltext_url' as url, api->'_source'->>'title' as title, normalize_title_v2(api->'_source'->>'title') as norm_title
    #     from crossref where response_jsonb->>'free_fulltext_url' in
    #     ( select url from (
    #     select response_jsonb->>'free_fulltext_url' as url, count(*) as c
    #     from crossref
    #     where crossref.response_jsonb->>'free_fulltext_url' is not null
    #     and id in (select id from dois_random_articles_1mil_do_hybrid_100k limit 100000)
    #     group by url
    #     order by c desc) s where c > 1 ) limit 1000 ) ss group by norm_title order by c desc
    # and then have added more to it

    common_title_string = """
        informationreaders
        informationcontributors
        editorialboardpublicationinformation
        insidefrontcovereditorialboard
        graphicalcontentslist
        instructionsauthors
        reviewsandnoticesbooks
        editorialboardaimsandscope
        contributorsthisissue
        parliamentaryintelligence
        editorialadvisoryboard
        informationauthors
        instructionscontributors
        royalsocietymedicine
        guesteditorsintroduction
        cumulativesubjectindexvolumes
        acknowledgementreviewers
        medicalsocietylondon
        ouvragesrecuslaredaction
        royalmedicalandchirurgicalsociety
        moderntechniquetreatment
        reviewcurrentliterature
        answerscmeexamination
        publishersannouncement
        cumulativeauthorindex
        abstractsfromcurrentliterature
        booksreceivedreview
        royalacademymedicineireland
        editorialsoftwaresurveysection
        cumulativesubjectindex
        acknowledgementreferees
        specialcorrespondence
        atmosphericelectricity
        classifiedadvertising
        softwaresurveysection
        abstractscurrentliterature
        britishmedicaljournal
        veranstaltungskalender
        internationalconference
        processintensification
        titlepageeditorialboard
        americanpublichealthassociation
        deepbrainstimulationparkinsonsdisease
        mathematicalmorphologyanditsapplicationssignalandimageprocessing
        principalcomponentanalysis
        acuterespiratorydistresssyndrome
        chronicobstructivepulmonarydisease
        fullscaleevaluationsocaptureincreasesemidryfgdtechnology
        conferenceannouncements
        thconferencecorporateentitiesmarketandeuropeandimensions
        postersessionabstracts
        britishjournaldermatology
        poincareandthreebodyproblem
        systemiclupuserythematosus
        bayeractivitiesdailylivingscalebadl
        mineralogicalsocietyamerica
        stsegmentelevationmyocardialinfarction
        systematicobservationcoachleadershipbehavioursyouthsport
        proximityawaremultiplemeshesdecimationusingquadricerrormetric
        radiochemicalandchemicalconstituentswaterselectedwellsandspringssouthernboundaryidahonationalengineeringandenvironmentallaboratoryhagermanareaidaho
        entrepreneurialleadership
        dictionaryepidemiology
        chieldcausalhypothesesevolutionarylinguisticsdatabase
        socialinequalitieshealth
        cancerincidenceandmortalitychina
        creativecommonseducatorsandlibrarians
        learningandsizegovernmentspendingmultiplier
        pensionreformolgmodelheterogeneousabilities
        congenitaldislocationhip
        endovasculartreatmentacuteischemicstroke
        corporatesocialresponsibility
        sustainableagriculture
        cambridgehandbookmultimedialearning
        """
    for common_title in common_title_string.split("\n"):
        if normalized_title == common_title.strip():
            return True
    return False


def is_known_mismatch(doi, pmh_id):
    mismatches = {
        '10.1063/1.4818552': [
            'hdl:10068/886851'  # thesis with same title
        ],
        '10.1016/j.conbuildmat.2019.116939': [
            'oai:repositorio.cuc.edu.co:11323/5292'  # abstract
        ],
        '10.1111/j.1439-0396.2010.01055.x': [
            'oai:dspace.uevora.pt:10174/3888'  # abstract
        ],
        '10.3233/ves-200717': [
            'oai:pure.atira.dk:publications/0eb5fb9c-4e41-4879-970a-78b53b7b078e'  # poster with same title
        ],
    }
    return pmh_id in mismatches.get(doi, [])


def oai_tag_match(tagname, record, return_list=False):
    if not tagname in record.metadata:
        return None
    matches = record.metadata[tagname]
    if return_list:
        return matches  # will be empty list if we found naught
    else:
        try:
            return matches[0]
        except IndexError:  # no matches.
            return None


def title_match_limit_exceptions():
    return {
        u'abinitiomoleculardynamicscdsequantumdotdopedglasses',
        u'speedingupdiscoveryauxeticzeoliteframeworksmachinelearning'
    }


class PmhRecord(db.Model):
    id = db.Column(db.Text, primary_key=True)
    repo_id = db.Column(db.Text) # delete once endpoint_ids are all populated
    endpoint_id = db.Column(db.Text)
    doi = db.Column(db.Text)
    record_timestamp = db.Column(db.DateTime)
    api_raw = db.Column(JSONB)
    title = db.Column(db.Text)
    license = db.Column(db.Text)
    oa = db.Column(db.Text)
    urls = db.Column(JSONB)
    authors = db.Column(JSONB)
    relations = db.Column(JSONB)
    sources = db.Column(JSONB)
    updated = db.Column(db.DateTime)
    rand = db.Column(db.Numeric)
    pmh_id = db.Column(db.Text)

    pages = db.relationship(
        # 'Page',
        'PageNew',
        lazy='select',   # lazy load
        cascade="all, delete-orphan",
        # don't want a backref because don't want page to link to this
        foreign_keys="PageNew.pmh_id"
    )

    @property
    def bare_pmh_id(self):
        return self.pmh_id or self.id

    def __init__(self, **kwargs):
        self.updated = datetime.datetime.utcnow().isoformat()
        super(self.__class__, self).__init__(**kwargs)

    def populate(self, endpoint_id, pmh_input_record, metadata_prefix='oai_dc'):
        self.updated = datetime.datetime.utcnow().isoformat()
        self.id = u'{}:{}'.format(endpoint_id, pmh_input_record.header.identifier)
        self.endpoint_id = endpoint_id
        self.pmh_id = pmh_input_record.header.identifier
        self.api_raw = pmh_input_record.raw
        self.record_timestamp = pmh_input_record.header.datestamp
        self.title = oai_tag_match("title", pmh_input_record)
        self.authors = oai_tag_match("creator", pmh_input_record, return_list=True)
        self.relations = oai_tag_match("relation", pmh_input_record, return_list=True)
        self.oa = oai_tag_match("oa", pmh_input_record)

        if metadata_prefix == 'qdc':
            self.license = oai_tag_match("rights.license", pmh_input_record)
        else:
            self.license = oai_tag_match("rights", pmh_input_record)

        self.sources = oai_tag_match("collname", pmh_input_record, return_list=True)

        identifier_matches = oai_tag_match("identifier", pmh_input_record, return_list=True)
        if self.pmh_id and self.pmh_id.startswith('oai:authors.library.caltech.edu'):
            identifier_matches = []

        identifier_doi_matches = oai_tag_match("identifier.doi", pmh_input_record, return_list=True)
        self.urls = self.get_good_urls(identifier_matches)

        if not self.urls:
            self.urls = self.get_good_urls(self.relations)

        possible_dois = []

        if self.relations:
            possible_dois += [s for s in self.relations if s and '/*ref*/' not in s and not s.startswith('reference')]
        if identifier_matches:
            possible_dois += [s for s in identifier_matches if s]
        if identifier_doi_matches:
            possible_dois += [s for s in identifier_doi_matches if s]

        if possible_dois:
            for possible_doi in possible_dois:
                if (
                    is_doi_url(possible_doi)
                    or possible_doi.startswith(u"doi:")
                    or re.findall(ur"10\.\d", possible_doi)
                ):
                    try:
                        doi_candidate = clean_doi(possible_doi)

                        if not doi_candidate:
                            continue

                        skip_these_doi_snippets = [
                            u'10.17605/osf.io',
                            u'10.14279/depositonce',
                            u'/(issn)',
                            u'10.17169/refubium',
                        ]
                        for doi_snippet in skip_these_doi_snippets:
                            if doi_snippet.lower() in doi_candidate.lower():
                                doi_candidate = None
                                break

                        if doi_candidate:
                            self.doi = doi_candidate
                    except NoDoiException:
                        pass

        self.doi = self._doi_override_by_id().get(self.bare_pmh_id, self.doi)
        self.title = self._title_override_by_id().get(self.bare_pmh_id, self.title)

    @staticmethod
    def _title_override_by_id():
        return {
            # wrong title
            u'oai:RePEc:feb:natura:00655': u'Do Workers Value Flexible Jobs? A Field Experiment On Compensating Differentials',
            # reviews of books with same title
            u'oai:ir.uiowa.edu:annals-of-iowa-11115': u'(Book Notice) The Bull Moose Years: Theodore Roosevelt and the Progressive Party',
            u'oai:ir.uiowa.edu:annals-of-iowa-9228': u'(Book Review) Land, Piety, Peoplehood: The Establishment of Mennonite Communities in America, 1683-1790',

            # published title changed slightly
            u'oai:figshare.com:article/10272041': u'Ab initio molecular dynamics of CdSe Quantum Dot-Doped Glasses',

            # ticket 6010. record links to PDF for different article.
            u'oai:eprints.uwe.ac.uk:33511': u'The Bristol-Bath Urban freight Consolidation Centre from the perspective of its users',
        }

    @staticmethod
    def _doi_override_by_id():
        return {
            # wrong DOI in identifier url
            u'oai:dspace.flinders.edu.au:2328/36108': u'10.1002/eat.22455',

            # picked up wrong DOI in relation
            u'oai:oai.kemsu.elpub.ru:article/2590': u'10.21603/2078-8975-2018-4-223-231',

            # junk in identifier
            u'oai:scholarspace.manoa.hawaii.edu:10125/42031': u'10.18357/ijih122201717783',

            # wrong DOI in relation
            u'oai:oai.perinatology.elpub.ru:article/560': u'10.21508/1027-4065-2017-62-5-111-118',

            u'oai:HAL:hal-00927061v2': u'10.1090/memo/1247',

            u'oai:revistas.ucm.es:article/62495': u'10.5209/clac.62495',

            u'oai:oro.open.ac.uk:57403': u'10.1090/hmath/011',

            u'oai:eprints.soas.ac.uk:22576': u'10.4324/9781315762210-8',

            u'oai:oai.mir.elpub.ru:article/838': u'10.18184/2079-4665.2018.9.3.338-350',

            u'oai:arXiv.org:1605.06120': None,

            u'oai:research-repository.griffith.edu.au:10072/80920': None,

            u'oai:HAL:cea-01550620v1': '10.1103/physrevb.93.214414',

            u'oai:ora.ox.ac.uk:uuid:f5740dd3-0b45-4e7b-8f2e-d4872a6c326c': '10.1016/j.jclinepi.2017.12.022',

            u'oai:ora.ox.ac.uk:uuid:a78ee943-6cfe-4fb9-859e-d7ec82ebec85': '10.1016/j.jclinepi.2019.05.033',

            u'oai:archive.ugent.be:3125191': None,

            u'oai:scholar.sun.ac.za:10019.1/95408': '10.4102/sajpsychiatry.v19i3.951',

            u'oai:rcin.org.pl:60213': None,

            u'oai:rcin.org.pl:48382': None,

            u'oai:philarchive.org/rec/LOGSTC': '10.1093/analys/anw051',

            u'oai:philarchive.org/rec/LOGMBK': '10.1111/1746-8361.12258',

            u'oai:CiteSeerX.psu:10.1.1.392.2251': None,

            u'oai:serval.unil.ch:BIB_289289AA7E27': None,  # oai:serval.unil.ch:duplicate of BIB_98991EE549F6
        }

    def get_good_urls(self, candidate_urls):
        valid_urls = []
        # pmc can only add pmc urls.  otherwise has junk about dois that aren't actually open.
        if candidate_urls:
            if "oai:pubmedcentral.nih.gov" in self.id:
                for url in candidate_urls:
                    if "/pmc/" in url and url != "http://www.ncbi.nlm.nih.gov/pmc/articles/PMC":
                        pmcid_matches = re.findall(".*(PMC\d+).*", url)
                        if pmcid_matches:
                            pmcid = pmcid_matches[0]
                            url = u"https://www.ncbi.nlm.nih.gov/pmc/articles/{}".format(pmcid)
                            valid_urls.append(url)
            else:
                valid_urls += [url for url in candidate_urls if url and url.startswith(u"http")]

        # filter out doi urls unless they are the only url
        # might be a figshare url etc, but otherwise is usually to a publisher page which
        # may or may not be open, and we are handling through hybrid path
        if len(valid_urls) > 1:
            valid_urls = [url for url in valid_urls if u"doi.org/" not in url]

        valid_urls = [url for url in valid_urls if u"doi.org/10.1111/" not in url]

        # filter out some urls that we know are closed or otherwise not useful
        blacklist_url_snippets = [
            u"/10.1093/analys/",
            u"academic.oup.com/analysis",
            u"analysis.oxfordjournals.org/",
            u"ncbi.nlm.nih.gov/pubmed/",
            u"gateway.webofknowledge.com/",
            u"orcid.org/",
            u"researchgate.net/",
            u"academia.edu/",
            u"europepmc.org/abstract/",
            u"ftp://",
            u"api.crossref",
            u"api.elsevier",
            u"api.osf",
            u"eprints.soton.ac.uk/413275",
            u"eprints.qut.edu.au/91459/3/91460.pdf",
            u"hdl.handle.net/2117/168732",
            u"hdl.handle.net/10044/1/81238",  # wrong article
            u"journals.elsevier.com",
        ]

        backlist_url_patterns = map(re.escape, blacklist_url_snippets) + [
            ur'springer.com/.*/journal/\d+$',
            ur'springer.com/journal/\d+$',
            ur'supinfo.pdf$',
            ur'Appendix[^/]*\.pdf$',
            ur'^https?://www\.icgip\.org/?$',
            ur'^https?://(www\.)?agu.org/journals/',
            ur'issue/current$',
            ur'/809AB601-EF05-4DD1-9741-E33D7847F8E5\.pdf$',
            ur'onlinelibrary\.wiley\.com/doi/.*/abstract',
            ur'https?://doi\.org/10\.1002/',  # wiley
            ur'https?://doi\.org/10\.1111/',  # wiley
            ur'authors\.library\.caltech\.edu/93971/\d+/41562_2019_595_MOESM',
            ur'aeaweb\.org/.*\.ds$',
            ur'aeaweb\.org/.*\.data$',
            ur'aeaweb\.org/.*\.appx$',
        ]

        for url_snippet in backlist_url_patterns:
            valid_urls = [url for url in valid_urls if not re.search(url_snippet, url)]


        # and then html unescape them, because some are html escaped
        h = HTMLParser()
        valid_urls = [h.unescape(url) for url in valid_urls]

        # make sure they are actually urls
        valid_urls = [url for url in valid_urls if url.startswith("http")]

        if self.bare_pmh_id.startswith('oai:ora.ox.ac.uk:uuid:') and not valid_urls:
            # https://ora.ox.ac.uk
            # pmh records don't have page urls but we can guess them
            # remove 'oai:ora.ox.ac.uk:' prefix and append to base URL
            valid_urls.append(u'https://ora.ox.ac.uk/objects/{}'.format(self.bare_pmh_id[len('oai:ora.ox.ac.uk:'):]))

        valid_urls = list(set(valid_urls))

        return valid_urls


    def mint_page_for_url(self, page_class, url):
        from page import PageNew
        # this is slow, but no slower then looking for titles before adding pages
        existing_page = PageNew.query.filter(PageNew.normalized_title==self.calc_normalized_title(),
                                             PageNew.match_type==page_class.__mapper_args__["polymorphic_identity"],
                                             PageNew.url==url,
                                             PageNew.endpoint_id==self.endpoint_id
                                             ).options(orm.noload('*')).first()
        if existing_page:
            my_page = existing_page
        else:
            my_page = page_class()
            my_page.url = url
            my_page.normalized_title = self.calc_normalized_title()
            my_page.endpoint_id = self.endpoint_id

        my_page.doi = self.doi
        my_page.title = self.title
        my_page.authors = self.authors
        my_page.record_timestamp = self.record_timestamp
        my_page.pmh_id = self.id
        my_page.repo_id = self.repo_id  # delete once endpoint_ids are all populated

        return my_page

    def calc_normalized_title(self):
        if not self.title:
            return None

        if self.endpoint_id == '63d70f0f03831f36129':
            # figshare. the record is for a figure but the title is from its parent article.
            return None

        working_title = self.title

        # repo specific rules
        # AMNH adds biblio to the end of titles, which ruins match.  remove this.
        # example http://digitallibrary.amnh.org/handle/2246/6816 oai:digitallibrary.amnh.org:2246/6816
        if "amnh.org" in self.id:
            # cut off the last part, after an openning paren
            working_title = re.sub(u"(Bulletin of.+no.+\d+)", "", working_title, re.IGNORECASE | re.MULTILINE)
            working_title = re.sub(u"(American Museum nov.+no.+\d+)", "", working_title, re.IGNORECASE | re.MULTILINE)

        # for endpoint 0dde28a908329849966, adds this to end of all titles, so remove (eg http://hdl.handle.net/11858/00-203Z-0000-002E-72BD-3)
        working_title = re.sub(u"vollständige digitalisierte Ausgabe", "", working_title, re.IGNORECASE | re.MULTILINE)
        return normalize_title(working_title)

    def delete_old_record(self):
        # old records used the bare record_id as pmh_record.id
        # delete the old record before merging, instead of conditionally updating or creating the new record
        db.session.query(PmhRecord).filter(
            PmhRecord.id == self.bare_pmh_id, PmhRecord.endpoint_id == self.endpoint_id
        ).delete()

    def mint_pages(self):
        if self.endpoint_id == 'ac9de7698155b820de7':
            # NIH PMC. Don't mint pages because we use a CSV dump to make OA locations. See Pub.ask_pmc
            return []

        self.pages = []

        # this should have already been done when setting .urls, but do it again in case there were improvements
        # case in point:  new url patterns added to the blacklist
        good_urls = self.get_good_urls(self.urls)

        for url in good_urls:
            if self.doi:
                my_page = self.mint_page_for_url(page.PageDoiMatch, url)
                self.pages.append(my_page)

            normalized_title = self.calc_normalized_title()
            if normalized_title:
                num_pages_with_this_normalized_title = db.session.query(page.PageTitleMatch.id).filter(page.PageTitleMatch.normalized_title==normalized_title).count()
                if num_pages_with_this_normalized_title >= 20 and normalized_title not in title_match_limit_exceptions():
                    logger.info(u"not minting page because too many with this title: {}".format(normalized_title))
                else:
                    my_page = self.mint_page_for_url(page.PageTitleMatch, url)
                    self.pages.append(my_page)
        # logger.info(u"minted pages: {}".format(self.pages))

        # delete pages with this pmh_id that aren't being updated
        db.session.query(page.PageNew).filter(
            page.PageNew.endpoint_id == self.endpoint_id,
            or_(page.PageNew.pmh_id == self.id, page.PageNew.pmh_id == self.pmh_id),
            page.PageNew.id.notin_([p.id for p in self.pages])
        ).delete(synchronize_session=False)

        return self.pages

    def __repr__(self):
        return u"<PmhRecord ({}) doi:{} '{}...'>".format(self.id, self.doi, self.title[0:20])

    def to_dict(self):
        response = {
            "oaipmh_id": self.bare_pmh_id,
            "oaipmh_record_timestamp": self.record_timestamp and self.record_timestamp.isoformat(),
            "urls": self.urls,
            "title": self.title
        }
        return response

