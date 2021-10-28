import re
from copy import deepcopy
from time import sleep

import requests
from lxml import etree

from app import logger


def parseland_response(parseland_api_url, retry_seconds):
    retry = True
    next_retry_interval = 1
    cumulative_wait = 0

    while retry:
        logger.info(f'trying {parseland_api_url}')
        response = requests.get(parseland_api_url)

        if response.ok:
            logger.info('got a 200 response from parseland')
            try:
                parseland_json = response.json()
                message = parseland_json.get('message', None)

                if isinstance(message, list):
                    # old-style response with authors at top level
                    return {'authors': message}
                elif isinstance(message, dict):
                    return message
                else:
                    logger.error("can't recognize parseland response format")
                    return None

            except ValueError as e:
                logger.error("response isn't valid json")
                return None
        else:
            logger.warning(f'got error response from parseland: {response}')

            if (
                response.status_code == 404
                and 'Source file not found' in response.text
                and cumulative_wait + next_retry_interval <= retry_seconds
            ):
                logger.info(f'retrying in {next_retry_interval} seconds')
                sleep(next_retry_interval)
                cumulative_wait += next_retry_interval
                next_retry_interval *= 1.5
            else:
                logger.info('not retrying')
                retry = False

    logger.info(f'done retrying after {cumulative_wait} seconds')
    return None


def parseland_parse(parseland_api_url, retry_seconds=0):
    parse = None

    if response := parseland_response(parseland_api_url, retry_seconds):
        parse = {'authors': [], 'published_date': None, 'genre': None}

        pl_authors = response.get('authors', [])
        logger.info(f'got {len(pl_authors)} authors')

        for pl_author in pl_authors:
            author = {'raw': pl_author.get('name'), 'affiliation': []}
            pl_affiliations = pl_author.get('affiliations')

            if isinstance(pl_affiliations, list):
                for pl_affiliation in pl_affiliations:
                    author['affiliation'].append({'name': pl_affiliation})

            if orcid := pl_author.get('orcid'):
                author['orcid'] = orcid

            parse['authors'].append(normalize_author(author))

        parse['published_date'] = response.get('published_date')
        parse['genre'] = response.get('genre')

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
        author['orcid'] = re.sub(r'.*((?:[0-9]{4}-){3}[0-9]{3}[0-9X]).*', r'\1', author['orcid'].upper())

    return author


def normalize_citation(citation):
    citation = deepcopy(citation)

    # https://api.crossref.org/swagger-ui/index.html#model-Reference

    for k in list(citation.keys()):
        if k != k.lower():
            citation[k.lower()] = citation[k]
            del citation[k]

    citation.setdefault('issn', None)
    citation.setdefault('standards-body', None)
    citation.setdefault('issue', None)
    citation.setdefault('key', None)
    citation.setdefault('series-title', None)
    citation.setdefault('isbn-type', None)
    citation.setdefault('doi-asserted-by', None)
    citation.setdefault('first-page', None)
    citation.setdefault('isbn', None)
    citation.setdefault('doi', None)
    citation.setdefault('component', None)
    citation.setdefault('article-title', None)
    citation.setdefault('volume-title', None)
    citation.setdefault('volume', None)
    citation.setdefault('author', None)
    citation.setdefault('standard-designator', None)
    citation.setdefault('year', None)
    citation.setdefault('unstructured', None)
    citation.setdefault('edition', None)
    citation.setdefault('journal-title', None)
    citation.setdefault('issn-type', None)

    return citation
