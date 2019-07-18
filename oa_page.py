"""
For some Pubs we can guess the url of a page that might have a fulltext link, but we're not confident enough to
just add it as a location directly.
For these we generate pages that will be scraped and matched to Pubs just like repository pages.
Special values of pmh_id indicate these pages where they must be handled differently from real pmh pages.

This module contains data and functions to generate candidate pages for a given Pub.
"""

from sqlalchemy import orm

import page


oa_publisher_equivalent = 'non-pmh-publisher-equivalent'


def make_oa_pages(pub):
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

    return [p for p in pages if not _existing_page(p)]


def _existing_page(p):
    return page.PageDoiMatch.query.filter(
        page.PageDoiMatch.doi == p.doi,
        page.PageNew.url == p.url,
        page.PageNew.pmh_id == oa_publisher_equivalent,
     ).options(orm.noload('*')).first()


def _cegh_pages(pub):
    """
    Clinical Epidemiology and Global Health urls can often be guessed
    from an alternative ID present in Crossref metadata.
    e.g. S2213398418300927 -> https://www.ceghonline.com/article/S2213-3984(18)30092-7/fulltext
    """
    alt_id = pub.crossref_alternative_id

    if alt_id and len(alt_id) == 17:
        url = 'https://www.ceghonline.com/article/{}/fulltext'.format(_format_alt_id(alt_id))

        return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=oa_publisher_equivalent)]
    else:
        return []


def _scichina_pages(pub):
    url = u'http://engine.scichina.com/doi/{}'.format(pub.id)
    return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=oa_publisher_equivalent)]


def _osi_pages(pub):
    alt_id = pub.crossref_alternative_id

    if alt_id:
        url = u'https://www.sciencedirect.com/science/article/pii/{}'.format(alt_id)
        return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=oa_publisher_equivalent)]
    else:
        return []


def _cjcatal_pages(pub):
    url = u'http://www.cjcatal.org/EN/{}'.format(pub.id)
    return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=oa_publisher_equivalent)]


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
        url = u'https://www.jstage.jst.go.jp/article/pdj/{}/{}/{}_{}_{}/_pdf'.format(
            volume, issue, volume, issue, page_no
        )
        return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=oa_publisher_equivalent)]

    return []


def _nnw_pages(pub):
    # pdf url looks like 10.14311/nnw.2016.26.006 -> http://nnw.cz/doi/2016/NNW.2016.26.006.pdf

    try:
        year = pub.id.split('.')[2]
        suffix = pub.id.split('/')[1].upper()
    except IndexError:
        return []

    if year and suffix:
        url = u'http://nnw.cz/doi/{}/{}.pdf'.format(
            year, suffix
        )
        return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=oa_publisher_equivalent)]

    return []


def _tacs_pages(pub):
    url = u'https://journals.lww.com/jtrauma/fulltext/{}'.format(pub.id)
    return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=oa_publisher_equivalent)]


def _format_alt_id(alt_id):
    return '{}-{}({}){}-{}'.format(
        alt_id[0:5],
        alt_id[5:9],
        alt_id[9:11],
        alt_id[11:16],
        alt_id[16:17]
    )