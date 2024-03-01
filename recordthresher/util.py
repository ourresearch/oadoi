import re
from copy import deepcopy
import time

import requests
from lxml import etree

from app import logger

ARXIV_ID_PATTERN = r'arXiv:\d{4}\.\d{4,5}(?:v\d+)?'


def pdf_parser_response(url):
    return parse_api_response(url, parser_name='pdf parser')


def parseland_response(url):
    return parseland_response(url)


def parse_api_response(url, parser_name='parseland'):
    start = time.time()
    logger.info(f'trying {url}')
    try:
        response = requests.get(url, verify=False)
        response_time = f'{time.time() - start:.2f}'
    except Exception as e:
        logger.exception(e)
        return None

    if response.ok:
        logger.info(
            f'got a 200 response from {parser_name} in {response_time} seconds')
        try:
            parseland_json = response.json()
            message = parseland_json.get('message', None)

            if isinstance(message, list):
                # old-style response with authors at top level
                return {'authors': message}
            elif isinstance(message, dict):
                return message
            else:
                logger.error(f"can't recognize {parser_name} response format")
                return None

        except ValueError as e:
            logger.error("response isn't valid json")
            return None
    else:
        logger.warning(
            f'got error response from {parser_name} in {response_time} seconds: {response}')


def parseland_parse(parseland_api_url):
    parse = None

    if response := parseland_response(parseland_api_url):
        parse = {'authors': [], 'published_date': None, 'genre': None,
                 'abstract': None}

        pl_authors = response.get('authors', [])
        logger.info(f'got {len(pl_authors)} authors')

        for pl_author in pl_authors:
            author = {
                'raw': pl_author.get('name'),
                'affiliation': [],
                'is_corresponding': pl_author.get('is_corresponding')
            }
            pl_affiliations = pl_author.get('affiliations')

            if isinstance(pl_affiliations, list):
                for pl_affiliation in pl_affiliations:
                    author['affiliation'].append({'name': pl_affiliation})

            if orcid := pl_author.get('orcid'):
                author['orcid'] = orcid

            parse['authors'].append(normalize_author(author))

        parse['published_date'] = response.get('published_date')
        parse['genre'] = response.get('genre')
        parse['abstract'] = response.get('abstract')
        parse['readable'] = response.get('readable')

    return parse


def xml_tree(xml, clean_namespaces=True):
    if not xml:
        return None

    try:
        tree = etree.fromstring(xml)

        if clean_namespaces:
            for e in tree.getiterator():
                e.tag = etree.QName(e).localname

            etree.cleanup_namespaces(tree)

        return tree
    except etree.ParseError as e:
        logger.exception(f'etree parse error: {e}')
        return None


def normalize_author(author):
    # https://api.crossref.org/swagger-ui/index.html#model-Author
    author = deepcopy(author)

    for k in list(author.keys()):
        if k != k.lower():
            author[k.lower()] = author[k]
            del author[k]

    author.setdefault('raw', None)

    if 'affiliations' in author and 'affiliation' not in author:
        author['affiliation'] = author['affiliations']
        del author['affiliations']

    author.setdefault('affiliation', [])

    for idx, affiliation in enumerate(author['affiliation']):
        if isinstance(affiliation, str):
            affiliation = {'name': affiliation}
            author['affiliation'][idx] = affiliation

        for k in list(affiliation.keys()):
            if k != k.lower():
                affiliation[k.lower()] = affiliation[k]
                del affiliation[k]

        affiliation.setdefault('name', None)

    author.setdefault('sequence', None)
    author.setdefault('name', None)
    author.setdefault('family', None)
    author.setdefault('orcid', None)
    author.setdefault('suffix', None)
    author.setdefault('authenticated-orcid', None)
    author.setdefault('given', None)

    if author['orcid']:
        author['orcid'] = re.sub(r'.*((?:[0-9]{4}-){3}[0-9]{3}[0-9X]).*', r'\1',
                                 author['orcid'].upper())

    return author


def normalize_citation(citation):
    citation = deepcopy(citation)

    # https://api.crossref.org/swagger-ui/index.html#model-Reference

    for k, v in list(citation.items()):
        if v is None:
            del citation[k]
        elif k != k.lower():
            citation[k.lower()] = v
            del citation[k]

    # citation.setdefault('issn', None)
    # citation.setdefault('standards-body', None)
    # citation.setdefault('issue', None)
    # citation.setdefault('key', None)
    # citation.setdefault('series-title', None)
    # citation.setdefault('isbn-type', None)
    # citation.setdefault('doi-asserted-by', None)
    # citation.setdefault('first-page', None)
    # citation.setdefault('isbn', None)
    # citation.setdefault('doi', None)
    # citation.setdefault('component', None)
    # citation.setdefault('article-title', None)
    # citation.setdefault('volume-title', None)
    # citation.setdefault('volume', None)
    # citation.setdefault('author', None)
    # citation.setdefault('standard-designator', None)
    # citation.setdefault('year', None)
    # citation.setdefault('unstructured', None)
    # citation.setdefault('edition', None)
    # citation.setdefault('journal-title', None)
    # citation.setdefault('issn-type', None)
    # citation.setdefault('pmid', None)

    return citation


def cleanup_affiliation(aff):
    aff = re.sub(r'^[a-z] +', '', aff)
    return re.sub(r' +', ' ', aff)
