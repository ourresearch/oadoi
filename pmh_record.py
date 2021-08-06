#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import html
import re

from sqlalchemy import or_, orm, text
from sqlalchemy.dialects.postgresql import JSONB

import page
from app import db
from app import logger
from util import NoDoiException
from util import clean_doi
from util import is_doi_url
from util import normalize_title

from unmatched_repo_page import UnmatchedRepoPage

DEBUG_BASE = False

_too_common_normalized_titles = None


def too_common_normalized_titles():
    global _too_common_normalized_titles
    if _too_common_normalized_titles is None:
        _too_common_normalized_titles = set([
            title for (title, ) in
            db.engine.execute(text('select normalized_title from common_normalized_titles'))
        ])
    return _too_common_normalized_titles


def title_is_too_short(normalized_title):
    if not normalized_title:
        return True
    return len(normalized_title) <= 21


def title_is_too_common(normalized_title):
    return normalized_title in too_common_normalized_titles()


def is_known_mismatch(doi, pmh_record):
    # screen figshare supplemental items, e.g.
    # https://doi.org/10.1021/ac035352d vs
    # https://api.figshare.com/v2/oai?verb=GetRecord&metadataPrefix=oai_dc&identifier=oai:figshare.com:article/3339307

    if pmh_record.bare_pmh_id and pmh_record.bare_pmh_id.startswith('oai:figshare.com'):
        if pmh_record.doi and pmh_record.doi.startswith('{}.s'.format(doi)):
            return True

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
        '10.1139/p79-106': [
            'oai:tsukuba.repo.nii.ac.jp:00011538'  # thesis with same title
        ],
        '10.1057/s41296-019-00346-8': [
            'oai:eprints.ucl.ac.uk.OAI2:10087912'  # wrong pdf on landing page
        ],
        '10.1201/9781315151823': [
            'oai:openresearch.lsbu.ac.uk:86zv0'  # doi belongs to book, pmh id belongs to chapter
        ],
        '10.1007/s00221-007-1163-1': [
            'oai:wrap.warwick.ac.uk:54523'  # thesis with same title
        ],
        '10.1080/08989621.2020.1860764': [
            'oai:generic.eprints.org:86138'  # pdf links don't work, http://irep.iium.edu.my/86138/
        ],
        '10.15866/irease.v11i4.14675': [
            'oai:generic.eprints.org:67164'  # screenshot of scopus
        ],
        '10.1016/b978-0-12-805393-5.00012-9': [
          'oai:CiteSeerX.psu:10.1.1.885.6937'  # title parsed incorrectly
        ],
        '10.1007/s10494-020-00126-0': [
            'oai:HAL:hal-02195059v1'  # conference paper with same title
        ],
        '10.1007/978-1-4614-7163-9_110149-1': [
            'oai:HAL:hal-01343052v1'  # conference paper with same title
        ],
        '10.1093/epolic/eiaa015': [
            # all different papers with same title
            'oai::82981',
            'oai::92620',
            'oai:RePEc:pra:mprapa:82981',
        ],
        '10.1063/1.5114468': [
            'oai:www.ucm.es:27329'  # conference paper and article with same title
        ],
        '10.1007/978-981-32-9620-6_9': [
            'oai:CiteSeerX.psu:10.1.1.434.2367' # citeseerx misfire
        ],
    }
    return pmh_record.bare_pmh_id in mismatches.get(doi, [])


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
        'abinitiomoleculardynamicscdsequantumdotdopedglasses',
        'speedingupdiscoveryauxeticzeoliteframeworksmachinelearning'
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
        self.id = '{}:{}'.format(endpoint_id, pmh_input_record.header.identifier)
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

        if self.pmh_id and self.pmh_id.startswith('oai:deepblue.lib.umich.edu'):
            # lots of identifiers and this item's is first
            identifier_matches.reverse()

        identifier_doi_matches = oai_tag_match("identifier.doi", pmh_input_record, return_list=True)
        self.urls = self.get_good_urls(identifier_matches)

        if not self.urls:
            self.urls = self.get_good_urls(self.relations)

        if not self.urls and self.pmh_id and self.pmh_id.startswith('oai:repozytorium.biblos.pk.edu.pl:'):
            rpk_id = self.pmh_id.split(':')[-1]
            self.urls = [f'https://repozytorium.biblos.pk.edu.pl/resources/{rpk_id}']

        possible_dois = []

        if self.relations:
            possible_dois += [s for s in self.relations if s and '/*ref*/' not in s and not s.startswith('reference')]

            if self.bare_pmh_id and self.bare_pmh_id.startswith('oai:openarchive.ki.se:'):
                # ticket 22247, relation DOIs are only for this article with this prefix
                possible_dois = [s for s in possible_dois if s.startswith('info:eu-repo/semantics/altIdentifier/doi/')]

        if identifier_matches:
            possible_dois += [s for s in identifier_matches if s]
        if identifier_doi_matches:
            possible_dois += [s for s in identifier_doi_matches if s]

        if possible_dois:
            for possible_doi in possible_dois:
                if (
                    is_doi_url(possible_doi)
                    or possible_doi.startswith("doi:")
                    or re.findall(r"10\.\d", possible_doi)
                ):
                    try:
                        doi_candidate = clean_doi(possible_doi)

                        if not doi_candidate:
                            continue

                        skip_these_doi_snippets = [
                            '10.17605/osf.io',
                            '10.14279/depositonce',
                            '/(issn)',
                            '10.17169/refubium',
                            '10.18452/', # DataCite
                        ]
                        skip_these_dois = [
                            '10.1002/9781118786352',  # journal
                        ]
                        for doi_snippet in skip_these_doi_snippets:
                            if doi_snippet.lower() in doi_candidate.lower():
                                doi_candidate = None
                                break

                        for skip_doi in skip_these_dois:
                            if skip_doi and doi_candidate and skip_doi.lower() == doi_candidate.lower():
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
            'oai:RePEc:feb:natura:00655': 'Do Workers Value Flexible Jobs? A Field Experiment On Compensating Differentials',
            # reviews of books with same title
            'oai:ir.uiowa.edu:annals-of-iowa-11115': '(Book Notice) The Bull Moose Years: Theodore Roosevelt and the Progressive Party',
            'oai:ir.uiowa.edu:annals-of-iowa-9228': '(Book Review) Land, Piety, Peoplehood: The Establishment of Mennonite Communities in America, 1683-1790',

            # published title changed slightly
            'oai:figshare.com:article/10272041': 'Ab initio molecular dynamics of CdSe Quantum Dot-Doped Glasses',

            # ticket 6010. record links to PDF for different article.
            'oai:eprints.uwe.ac.uk:33511': 'The Bristol-Bath Urban freight Consolidation Centre from the perspective of its users',

            'oai:www.duo.uio.no:10852/77974': 'Chronic pain among the hospitalized patients after the 22nd july-2011 terror attacks in Oslo and at Utøya Island.',
        }

    @staticmethod
    def _doi_override_by_id():
        return {
            # wrong DOI in identifier url
            'oai:dspace.flinders.edu.au:2328/36108': '10.1002/eat.22455',

            # picked up wrong DOI in relation
            'oai:oai.kemsu.elpub.ru:article/2590': '10.21603/2078-8975-2018-4-223-231',

            # junk in identifier
            'oai:scholarspace.manoa.hawaii.edu:10125/42031': '10.18357/ijih122201717783',

            # wrong DOI in relation
            'oai:oai.perinatology.elpub.ru:article/560': '10.21508/1027-4065-2017-62-5-111-118',

            'oai:HAL:hal-00927061v2': '10.1090/memo/1247',

            'oai:revistas.ucm.es:article/62495': '10.5209/clac.62495',

            'oai:oro.open.ac.uk:57403': '10.1090/hmath/011',

            'oai:eprints.soas.ac.uk:22576': '10.4324/9781315762210-8',

            'oai:oai.mir.elpub.ru:article/838': '10.18184/2079-4665.2018.9.3.338-350',

            'oai:arXiv.org:1605.06120': None,

            'oai:research-repository.griffith.edu.au:10072/80920': None,

            'oai:HAL:cea-01550620v1': '10.1103/physrevb.93.214414',

            'oai:ora.ox.ac.uk:uuid:f5740dd3-0b45-4e7b-8f2e-d4872a6c326c': '10.1016/j.jclinepi.2017.12.022',

            'oai:ora.ox.ac.uk:uuid:a78ee943-6cfe-4fb9-859e-d7ec82ebec85': '10.1016/j.jclinepi.2019.05.033',

            'oai:archive.ugent.be:3125191': None,

            'oai:scholar.sun.ac.za:10019.1/95408': '10.4102/sajpsychiatry.v19i3.951',

            'oai:rcin.org.pl:60213': None,

            'oai:rcin.org.pl:48382': None,

            'oai:philarchive.org/rec/LOGSTC': '10.1093/analys/anw051',

            'oai:philarchive.org/rec/LOGMBK': '10.1111/1746-8361.12258',

            'oai:CiteSeerX.psu:10.1.1.392.2251': None,

            'oai:serval.unil.ch:BIB_289289AA7E27': None,  # oai:serval.unil.ch:duplicate of BIB_98991EE549F6

            'oai:deepblue.lib.umich.edu:2027.42/141967': '10.1111/asap.12132',

            'oai:eprints.lancs.ac.uk:80508': None,  # says 10.1057/978-1-137-58629-2, but that's the book holding this chapter

            'oai:zenodo.org:3994623': '10.1007/978-3-319-29791-0',

            'oai:elib.dlr.de:136158': None,  # chapter of 10.1007/978-3-030-48340-1

            'oai:wrap.warwick.ac.uk:147355': '10.1177/0022242921992052',

            'oai:www.zora.uzh.ch:133251': None,

            'oai:ray.yorksj.ac.uk:2511': None,  # record is chapter, DOI is book

            'oai:intellectum.unisabana.edu.co:10818/20216': None,  # all DOIs are citations

            'oai:cris.maastrichtuniversity.nl:publications/494aa88b-4a2b-4b81-b926-8005af3f85d5': None,  # record is chapter, DOI is book

            'oai:repository.ucatolica.edu.co:10983/22919': '10.14718/revarq.2018.20.2.1562',

            'oai:HAL:halshs-03107637v1': None,  # record is chapter, DOI 10.1515/9781614514909 is book

            'oai:eprints.bbk.ac.uk.oai2:28966': '10.1007/978-3-030-29736-7_11',  # book chapter

            'oai:dspace.library.uvic.ca:1828/11889': None,

            'oai:real.mtak.hu:122999': None,

            'oai:real.mtak.hu:121388': None,
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
                            url = "https://www.ncbi.nlm.nih.gov/pmc/articles/{}".format(pmcid)
                            valid_urls.append(url)
            else:
                if self.endpoint_id == 'ycf3gzxeiyuw3jqwjmx3':  # https://lirias.kuleuven.be
                    candidate_urls = [re.sub(r'^\d+;http', 'http', url) for url in candidate_urls if url]

                valid_urls += [url for url in candidate_urls if url and url.startswith("http")]

        # filter out doi urls unless they are the only url
        # might be a figshare url etc, but otherwise is usually to a publisher page which
        # may or may not be open, and we are handling through hybrid path

        use_doi_url_id_prefixes = [
            'cdr.lib.unc.edu:'
        ]

        use_doi_url = False
        for use_doi_url_id_prefix in use_doi_url_id_prefixes:
            if self.bare_pmh_id and self.bare_pmh_id.startswith(use_doi_url_id_prefix):
                use_doi_url = True
                break

        if not use_doi_url and len(valid_urls) > 1:
            valid_urls = [url for url in valid_urls if "doi.org/" not in url]

        valid_urls = [url for url in valid_urls if "doi.org/10.1111/" not in url]


        if self.bare_pmh_id and self.bare_pmh_id.startswith('oai:alma.61RMIT_INST:'):
            valid_urls = [url for url in valid_urls if 'rmit.edu.au' in url]

        # filter out some urls that we know are closed or otherwise not useful
        blacklist_url_snippets = [
            "/10.1093/analys/",
            "academic.oup.com/analysis",
            "analysis.oxfordjournals.org/",
            "ncbi.nlm.nih.gov/pubmed/",
            "gateway.webofknowledge.com/",
            "orcid.org/",
            "researchgate.net/",
            "academia.edu/",
            "europepmc.org/abstract/",
            "ftp://",
            "api.crossref",
            "api.elsevier",
            "api.osf",
            "eprints.soton.ac.uk/413275",
            "eprints.qut.edu.au/91459/3/91460.pdf",
            "hdl.handle.net/2117/168732",
            "hdl.handle.net/10044/1/81238",  # wrong article
            "journals.elsevier.com",
            "https://hdl.handle.net/10037/19572",  # copyright violation. ticket 22259
            "http://irep.iium.edu.my/58547/9/Antibiotic%20dosing%20during%20extracorporeal%20membrane%20oxygenation.pdf",
            "oceanrep.geomar.de/52096/7/s41586-021-03496-1.pdf",
        ]

        backlist_url_patterns = list(map(re.escape, blacklist_url_snippets)) + [
            r'springer.com/.*/journal/\d+$',
            r'springer.com/journal/\d+$',
            r'supinfo.pdf$',
            r'Appendix[^/]*\.pdf$',
            r'^https?://www\.icgip\.org/?$',
            r'^https?://(www\.)?agu.org/journals/',
            r'issue/current$',
            r'/809AB601-EF05-4DD1-9741-E33D7847F8E5\.pdf$',
            r'onlinelibrary\.wiley\.com/doi/',
            r'https?://doi\.org/10\.1002/',  # wiley
            r'https?://doi\.org/10\.1111/',  # wiley
            r'authors\.library\.caltech\.edu/93971/\d+/41562_2019_595_MOESM',
            r'aeaweb\.org/.*\.ds$',
            r'aeaweb\.org/.*\.data$',
            r'aeaweb\.org/.*\.appx$',
            r'https?://dspace\.stir\.ac\.uk/.*\.jpg$',
            r'https?://dspace\.stir\.ac\.uk/.*\.tif$',
            r'/table_final\.pdf$',
            r'/supplemental_final\.pdf$',
            r'psasir\.upm\.edu\.my/id/eprint/36880/1/Conceptualizing%20and%20measuring%20youth\.pdf',
            r'psasir\.upm\.edu\.my/id/eprint/53326/1/Conceptualizing%20and%20measuring%20youth\.pdf',
            r'^https?://(www\.)?tandfonline\.com/toc/',
            r'\dSuppl\.pdf$',
            r'^https://lirias\.kuleuven\.be/handle/\d+/\d+$',
            r'^https?://eu\.wiley\.com/',
            r'^https?://www\.wiley\.com/',
            r'hull-repository\.worktribe\.com/(\w+/)?437540(/|$)',
        ]

        for url_snippet in backlist_url_patterns:
            valid_urls = [url for url in valid_urls if not re.search(url_snippet, url)]

        supplemental_url_patterns = [
            r'Figures.pdf$',
        ]

        if len(valid_urls) > 1:
            for url_pattern in supplemental_url_patterns:
                valid_urls = [url for url in valid_urls if not re.search(url_pattern, url)]

        # and then html unescape them, because some are html escaped
        valid_urls = [html.unescape(url) for url in valid_urls]

        # make sure they are actually urls
        valid_urls = [url for url in valid_urls if url.startswith("http")]

        if self.bare_pmh_id.startswith('oai:ora.ox.ac.uk:uuid:') and not valid_urls:
            # https://ora.ox.ac.uk
            # pmh records don't have page urls but we can guess them
            # remove 'oai:ora.ox.ac.uk:' prefix and append to base URL
            valid_urls.append('https://ora.ox.ac.uk/objects/{}'.format(self.bare_pmh_id[len('oai:ora.ox.ac.uk:'):]))

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

    def mint_unmatched_page_for_url(self, url):
        unmatched_page = UnmatchedRepoPage(self.endpoint_id, self.id, url)
        unmatched_page.title = self.title
        unmatched_page.normalized_title = self.calc_normalized_title()
        unmatched_page.record_timestamp = self.record_timestamp
        return unmatched_page

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
            working_title = re.sub("(Bulletin of.+no.+\d+)", "", working_title, re.IGNORECASE | re.MULTILINE)
            working_title = re.sub("(American Museum nov.+no.+\d+)", "", working_title, re.IGNORECASE | re.MULTILINE)

        # for endpoint 0dde28a908329849966, adds this to end of all titles, so remove (eg http://hdl.handle.net/11858/00-203Z-0000-002E-72BD-3)
        working_title = re.sub("vollständige digitalisierte Ausgabe", "", working_title, re.IGNORECASE | re.MULTILINE)
        return normalize_title(working_title)

    def delete_old_record(self):
        # old records used the bare record_id as pmh_record.id
        # delete the old record before merging, instead of conditionally updating or creating the new record
        db.session.query(PmhRecord).filter(
            PmhRecord.id == self.bare_pmh_id, PmhRecord.endpoint_id == self.endpoint_id
        ).delete()

    def mint_pages(self, reset_scrape_date=False):
        if self.endpoint_id == 'ac9de7698155b820de7':
            # NIH PMC. Don't mint pages because we use a CSV dump to make OA locations. See Pub.ask_pmc
            return []

        if self.bare_pmh_id and self.bare_pmh_id.startswith('oai:openarchive.ki.se:'):
            # ticket 22247, only type=art can match DOIs
            if '<dc:type>art</dc:type>' not in self.api_raw:
                return []

        self.pages = []

        # this should have already been done when setting .urls, but do it again in case there were improvements
        # case in point:  new url patterns added to the blacklist
        good_urls = self.get_good_urls(self.urls)

        if re.compile(r'<dc:rights>Limited Access</dc:rights>', re.MULTILINE).findall(self.api_raw):
            logger.info('found limited access label, not minting pages')
        else:
            for url in good_urls:
                if self.endpoint_id and self.pmh_id:
                    db.session.merge(self.mint_unmatched_page_for_url(url))

                if self.doi:
                    my_page = self.mint_page_for_url(page.PageDoiMatch, url)
                    self.pages.append(my_page)

                normalized_title = self.calc_normalized_title()
                if normalized_title:
                    num_pages_with_this_normalized_title = db.session.query(page.PageTitleMatch.id).filter(page.PageTitleMatch.normalized_title==normalized_title).count()
                    if num_pages_with_this_normalized_title >= 20 and normalized_title not in title_match_limit_exceptions():
                        logger.info("not minting page because too many with this title: {}".format(normalized_title))
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

        if reset_scrape_date and self.pages:
            # move already queued-pages at the front of the queue
            # if the record was updated the oa status might have changed
            query_text = '''
                update page_green_scrape_queue
                set finished = null
                where id = any(:ids) and started is null
            '''

            reset_query = text(query_text).bindparams(ids=[p.id for p in self.pages])

            db.session.execute(reset_query)

        return self.pages

    def __repr__(self):
        return "<PmhRecord ({}) doi:{} '{}...'>".format(self.id, self.doi, self.title[0:20])

    def to_dict(self):
        response = {
            "oaipmh_id": self.bare_pmh_id,
            "oaipmh_record_timestamp": self.record_timestamp and self.record_timestamp.isoformat(),
            "urls": self.urls,
            "title": self.title
        }
        return response

