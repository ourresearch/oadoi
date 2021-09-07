"""
For some Pubs we can guess the url of a page that might have a fulltext link, but we're not confident enough to
just add it as a location directly.
For these we generate pages that will be scraped and matched to Pubs just like repository pages.
Special values of pmh_id indicate these pages where they must be handled differently from real pmh pages.

This module contains data and functions to generate candidate pages for a given Pub.
"""

import re

from sqlalchemy import orm

import page
import repo_page

publisher_equivalent_pmh_id = 'non-pmh-publisher-equivalent'
publisher_equivalent_endpoint_id = 'cwvu6nh268xnnawemzp2'
biorxiv_endpoint_id = 'tvyradgqys4ex4yosqvk'
medrxiv_endpoint_id = 'gwydfmmgqtojcs3hvzsa'
research_square_endpoint_id = 'ukj4nbc7x7tofm5j6m9p'
scielo_endpoint_id = 'wcmexgsfmvbrdjzx4l5m'
authorea_endpoint_id = 'mgm3w2hszwdghkrnkrms'
eartharxiv_endpoint_id = 'l6r8fqxf84hg3xuqslkj'


def _biorxiv_pmh_id(doi):
    return 'bioRxiv:{}'.format(doi)


def _medrxiv_pmh_id(doi):
    return 'medRxiv:{}'.format(doi)


def _research_square_pmh_id(doi):
    return 'ResearchSquare:{}'.format(doi)


def _scielo_pmh_id(doi):
    return 'SciELO:{}'.format(doi)


def _authorea_pmh_id(doi):
    return 'Authorea:{}'.format(doi)


def _eartharxiv_pmh_id(doi):
    return 'EarthArXiv:{}'.format(doi)


def make_oa_pages(pub):
    pages = []
    pages.extend(make_publisher_equivalent_pages(pub))
    pages.extend(make_biorxiv_pages(pub))
    pages.extend(make_research_square_pages(pub))
    pages.extend(make_scielo_preprint_pages(pub))
    pages.extend(make_authorea_pages(pub))
    pages.extend(make_eartharxiv_pages(pub))
    return pages


def _pmh_authors(pub):
    authors = []
    for author in pub.authors or []:
        name_parts = []
        try:
            name_parts.append(author['family'])
        except (AttributeError, TypeError, KeyError):
            pass

        try:
            name_parts.append((author['given']))
        except (AttributeError, TypeError, KeyError):
            pass

        if name_parts:
            authors.append(', '.join(name_parts))

    return authors


def make_biorxiv_pages(pub):
    if pub.doi.startswith('10.1101/') and pub.genre == 'posted-content':
        url = 'https://doi.org/{}'.format(pub.doi)

        pmh_page = repo_page.RepoPage()
        pmh_page.url = url
        pmh_page.doi = pub.doi
        pmh_page.title = pub.title
        pmh_page.normalized_title = pub.normalized_title
        pmh_page.authors = _pmh_authors(pub)
        pmh_page.scrape_version = 'submittedVersion'
        pmh_page.scrape_metadata_url = url
        pmh_page.match_title = True

        xref_institution = pub.crossref_api_raw_new.get('institution', {})
        if isinstance(xref_institution, list) and xref_institution:
            xref_institution = xref_institution[0]

        if xref_institution:
            xref_institution_name = xref_institution.get('name', None)
        else:
            xref_institution_name = None

        if xref_institution_name == 'medRxiv':
            pmh_page.pmh_id = _medrxiv_pmh_id(pub.doi)
            pmh_page.endpoint_id = medrxiv_endpoint_id
        else:
            pmh_page.pmh_id = _biorxiv_pmh_id(pub.doi)
            pmh_page.endpoint_id = biorxiv_endpoint_id

        if _existing_page(repo_page.RepoPage, pmh_page.url, pmh_page.pmh_id):
            return []
        else:
            return [pmh_page]
    else:
        return []


def make_research_square_pages(pub):
    if pub.doi.startswith('10.21203/rs.') and pub.genre == 'posted-content':
        url = 'https://doi.org/{}'.format(pub.doi)

        pmh_page = repo_page.RepoPage
        pmh_page.pmh_id = _research_square_pmh_id(pub.doi)
        pmh_page.url = url
        pmh_page.doi = pub.doi
        pmh_page.title = pub.title
        pmh_page.normalized_title = pub.normalized_title
        pmh_page.authors = _pmh_authors(pub)
        pmh_page.endpoint_id = research_square_endpoint_id
        pmh_page.scrape_version = 'submittedVersion'
        pmh_page.scrape_metadata_url = url
        pmh_page.match_title = True

        if _existing_page(repo_page.RepoPage, pmh_page.url, pmh_page.pmh_id):
            return []
        else:
            return [pmh_page]
    else:
        return []


def make_scielo_preprint_pages(pub):
    if pub.publisher and 'scielo' in pub.publisher.lower() and pub.genre == 'posted-content':
        url = 'https://doi.org/{}'.format(pub.doi)

        pmh_page = repo_page.RepoPage()
        pmh_page.pmh_id = _scielo_pmh_id(pub.doi)
        pmh_page.url = url
        pmh_page.doi = pub.doi
        pmh_page.title = pub.title
        pmh_page.normalized_title = pub.normalized_title
        pmh_page.authors = _pmh_authors(pub)
        pmh_page.endpoint_id = scielo_endpoint_id
        pmh_page.scrape_version = 'submittedVersion'
        pmh_page.scrape_metadata_url = url
        pmh_page.match_title = True

        if _existing_page(repo_page.RepoPage, pmh_page.url, pmh_page.pmh_id):
            return []
        else:
            return [pmh_page]
    else:
        return []


def make_authorea_pages(pub):
    if pub.publisher and 'authorea' in pub.publisher.lower() and pub.genre == 'posted-content':
        url = 'https://doi.org/{}'.format(pub.doi)

        pmh_page = repo_page.RepoPage()
        pmh_page.pmh_id = _authorea_pmh_id(pub.doi)
        pmh_page.url = url
        pmh_page.doi = pub.doi
        pmh_page.title = pub.title
        pmh_page.normalized_title = pub.normalized_title
        pmh_page.authors = _pmh_authors(pub)
        pmh_page.endpoint_id = authorea_endpoint_id
        pmh_page.scrape_version = 'submittedVersion'
        pmh_page.scrape_metadata_url = url
        pmh_page.match_title = True

        if _existing_page(repo_page.RepoPage, pmh_page.url, pmh_page.pmh_id):
            return []
        else:
            return [pmh_page]
    else:
        return []


def make_eartharxiv_pages(pub):
    if pub.doi.startswith('10.31223/') and pub.publisher and 'california digital library' in pub.publisher.lower() and pub.genre == 'posted-content':
        url = 'https://doi.org/{}'.format(pub.doi)

        pmh_page = repo_page.RepoPage
        pmh_page.pmh_id = _eartharxiv_pmh_id(pub.doi)
        pmh_page.url = url
        pmh_page.doi = pub.doi
        pmh_page.title = pub.title
        pmh_page.normalized_title = pub.normalized_title
        pmh_page.authors = _pmh_authors(pub)
        pmh_page.endpoint_id = eartharxiv_endpoint_id
        pmh_page.scrape_version = 'submittedVersion'
        pmh_page.scrape_metadata_url = url
        pmh_page.match_title = True

        if _existing_page(repo_page.RepoPage, pmh_page.url, pmh_page.pmh_id):
            return []
        else:
            return [pmh_page]
    else:
        return []


def make_publisher_equivalent_pages(pub):
    pages = []

    if pub.issns:
        # Clinical Epidemiology and Global Health
        if '2213-3984' in pub.issns:
            pages.extend(_cegh_pages(pub))

        # Science Bulletin
        if '2095-9273' in pub.issns:
            pages.extend(_scichina_pages(pub))

        # Oral Science International
        if '1348-8643' in pub.issns:
            pages.extend(_osi_pages(pub))

        # Chinese Journal of Catalysis
        if '1872-2067' in pub.issns:
            pages.extend(_cjcatal_pages(pub))

        # Journal of Energy Chemistry
        if '2095-4956' in pub.issns:
            pages.extend(_scichina_pages(pub))

        # Pediatric Dental Journal
        if '0917-2394' in pub.issns:
            pages.extend(_pdj_pages(pub))

        # Neural Network World
        if '1210-0552' in pub.issns or '2336-4335' in pub.issns:
            pages.extend(_nnw_pages(pub))

        # Journal of Trauma and Acute Care Surgery
        if '2163-0755' in pub.issns:
            pages.extend(_tacs_pages(pub))

        # Journal of Chemical Sciences
        if pub.issn_l == '0253-4134':
            pages.extend(_jcs_pages(pub))

        # Bulletin of Materials Science
        if pub.issn_l == '0250-4707':
            pages.extend(_boms_pages(pub))

        # Sadhana
        if pub.issn_l == '0256-2499':
            pages.extend(_sadhana_pages(pub))

        # Journal of Earth System Science
        if pub.issn_l == '0253-4126':
            pages.extend(_jess_pages(pub))

        # Journal of Meteorological Research
        if pub.issn_l == '2095-6037':
            pages.extend(_jmr_pages(pub))

        # Acta Metallurgica Sinica (English Letters)
        if pub.issn_l == '1006-7191':
            pages.extend(_ams_pages(pub))

        # Journal of Geographical Sciences
        if pub.issn_l == '1009-637X':
            pages.extend(_jgs_pages(pub))

        # Chinese Journal of Polymer Science
        if pub.issn_l == '0256-7679':
            pages.extend(_cjps_pages(pub))

        # Journal of Arid Land
        if pub.issn_l == '1674-6767':
            pages.extend(_jal_pages(pub))

        # China Ocean Engineering
        if pub.issn_l == '0890-5487':
            pages.extend(_coe_pages(pub))

        # Science China Information Sciences
        if pub.issn_l == '1869-1919':
            pages.extend(_scichina_pages(pub))

        # Chinese Geographical Science
        if pub.issn_l == '1002-0063':
            pages.extend(_cgs_pages(pub))

        # Geodiversitas
        if pub.issn_l == '1280-9659':
            pages.extend(_geodiversitas_pages(pub))

        # Archives of Physical Medicine and Rehabilitation
        if pub.issn_l == '0003-9993':
            pages.extend(_apmr_pages(pub))

    return [p for p in pages if not _existing_page(repo_page.RepoPage, p.url, p.pmh_id)]


def _existing_page(page_class, url, pmh_id):
    return page.PageNew.query.filter(
        page.PageNew.match_type == page_class.match_type,
        page.PageNew.url == url,
        page.PageNew.pmh_id == pmh_id
    ).options(orm.noload('*')).first()


def _coe_pages(pub):
    url = 'http://www.chinaoceanengin.cn/article/doi/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _jal_pages(pub):
    url = 'http://jal.xjegi.com/EN/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _cjps_pages(pub):
    url = 'http://www.cjps.org/article/doi/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _jgs_pages(pub):
    url = 'http://www.geogsci.com/EN/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _cgs_pages(pub):
    url = 'http://egeoscien.neigae.ac.cn/EN/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _ams_pages(pub):
    url = 'http://www.amse.org.cn/EN/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _jmr_pages(pub):
    url = 'http://jmr.cmsjournal.net/article/doi/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _jcs_pages(pub):
    return _ias_pages(pub, 'jcsc')


def _boms_pages(pub):
    return _ias_pages(pub, 'boms')


def _sadhana_pages(pub):
    return _ias_pages(pub, 'sadh')


def _jess_pages(pub):
    return _ias_pages(pub, 'jess')


def _ias_pages(pub, journal_abbr):
    # landing page looks like https://www.ias.ac.in/describe/article/jcsc/121/06/1077-1081
    # journal abbr / volume / issue / pages

    try:
        volume = '{:03d}'.format(int(pub.crossref_api_raw['volume']))
        issue = '{:02d}'.format(int(pub.crossref_api_raw['issue']))
        if 'page' in pub.crossref_api_raw_new:
            pages = '-'.join(['{:04d}'.format(int(p)) for p in pub.crossref_api_raw['page'].split('-')])
        else:
            pages = '{:04d}'.format(int(pub.crossref_api_raw_new['article-number']))
    except (KeyError, ValueError, TypeError):
        # don't try too hard, give up if anything was missing or looks weird
        return []

    if volume and issue and pages:
        url = 'https://www.ias.ac.in/describe/article/{}/{}/{}/{}'.format(
            journal_abbr, volume, issue, pages
        )
        return [_publisher_page(url, pub.doi)]

    return []


def _cegh_pages(pub):
    """
    Clinical Epidemiology and Global Health urls can often be guessed
    from an alternative ID present in Crossref metadata.
    e.g. S2213398418300927 -> https://www.ceghonline.com/article/S2213-3984(18)30092-7/fulltext
    """
    alt_id = pub.crossref_alternative_id

    if alt_id and len(alt_id) == 17:
        url = 'https://www.ceghonline.com/article/{}/fulltext'.format(_format_alt_id(alt_id))

        return [_publisher_page(url, pub.doi)]
    else:
        return []


def _scichina_pages(pub):
    return []


def _osi_pages(pub):
    alt_id = pub.crossref_alternative_id

    if alt_id:
        url = 'https://www.sciencedirect.com/science/article/pii/{}'.format(alt_id)
        return [_publisher_page(url, pub.doi)]
    else:
        return []


def _cjcatal_pages(pub):
    url = 'http://www.cjcatal.org/EN/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _pdj_pages(pub):
    # pdf url looks like https://www.jstage.jst.go.jp/article/pdj/15/1/15_1_120/_pdf

    try:
        volume = int(pub.crossref_api_raw['volume'])
        issue = int(pub.crossref_api_raw['issue'])
        page_no = int(pub.crossref_api_raw['page'].split('-')[0])
    except (KeyError, ValueError, TypeError):
        # don't try too hard, give up if anything was missing or looks weird
        return []

    if volume and issue and page_no:
        url = 'https://www.jstage.jst.go.jp/article/pdj/{}/{}/{}_{}_{}/_pdf'.format(
            volume, issue, volume, issue, page_no
        )
        return [_publisher_page(url, pub.doi)]

    return []


def _nnw_pages(pub):
    # pdf url looks like 10.14311/nnw.2016.26.006 -> http://nnw.cz/doi/2016/NNW.2016.26.006.pdf

    try:
        year = pub.id.split('.')[2]
        suffix = pub.id.split('/')[1].upper()
    except IndexError:
        return []

    if year and suffix:
        url = 'http://nnw.cz/doi/{}/{}.pdf'.format(
            year, suffix
        )
        return [_publisher_page(url, pub.doi)]

    return []


def _tacs_pages(pub):
    url = 'https://journals.lww.com/jtrauma/fulltext/{}'.format(pub.id)
    return [_publisher_page(url, pub.doi)]


def _geodiversitas_pages(pub):
    # 10.5252/geodiversitas2018v40a15 ->
    # http://sciencepress.mnhn.fr/en/periodiques/geodiversitas/40/15

    suffix = re.search(r'\d+a\d+$', pub.doi)
    if not suffix:
        return []

    volume = suffix.group(0).split('a')[0]
    article = suffix.group(0).split('a')[1]

    url = 'http://sciencepress.mnhn.fr/en/periodiques/geodiversitas/{}/{}'.format(volume, article)

    return [_publisher_page(url, pub.doi)]


def _apmr_pages(pub):
    # 10.1016/0003-9993(92)90010-t ->
    # https://www.archives-pmr.org/article/0003-9993(92)90010-T/fulltext

    try:
        suffix = pub.id.split('/')[1].upper()
        url = f'https://www.archives-pmr.org/article/{suffix}/fulltext'
        return [_publisher_page(url, pub.doi)]
    except (IndexError, AttributeError):
        return []


def _publisher_page(url, doi):
    return repo_page.RepoPage(
        url=url,
        doi=doi,
        pmh_id=publisher_equivalent_pmh_id,
        endpoint_id=publisher_equivalent_endpoint_id,
        match_doi=True
    )


def _format_alt_id(alt_id):
    return '{}-{}({}){}-{}'.format(
        alt_id[0:5],
        alt_id[5:9],
        alt_id[9:11],
        alt_id[11:16],
        alt_id[16:17]
    )