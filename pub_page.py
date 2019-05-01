"""
For some Pubs we can guess the url of a page that might have a fulltext link, but we're not confident enough to
just add it as a location directly.
For these we generate pages that will be scraped and matched to Pubs just like repository pages.
This module contains data and functions to generate candidate pages for a given Pub.
"""

from sqlalchemy import orm

import page

publisher_equivalent = 'publisher-equivalent page'


def get_pages(pub):
    pages = []

    if pub.issns and '2213-3984' in pub.issns:
        pages.extend(cegh_pages(pub))

    return [p for p in pages if not _existing_page(p)]


def _existing_page(p):
    return page.PageDoiMatch.query.filter(
        page.PageDoiMatch.doi == p.doi,
        page.PageNew.url == p.url,
        page.PageNew.pmh_id.is_(None)
     ).options(orm.noload('*')).first()


def cegh_pages(pub):
    """
    Clinical Epidemiology and Global Health urls can often be guessed
    from an alternative ID present in Crossref metadata.
    e.g. S2213398418300927 -> https://www.ceghonline.com/article/S2213-3984(18)30092-7/fulltext
    """
    alt_id = pub.crossref_alternative_id

    if alt_id and len(alt_id) == 17:
        url = 'https://www.ceghonline.com/article/{}-{}({}){}-{}/fulltext'.format(
            alt_id[0:5],
            alt_id[5:9],
            alt_id[9:11],
            alt_id[11:16],
            alt_id[16:17]
        )

        return [page.PageDoiMatch(url=url, doi=pub.id, pmh_id=publisher_equivalent)]
    else:
        return []

