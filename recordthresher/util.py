import re
from copy import deepcopy


def normalize_author(author):
    # https://api.crossref.org/swagger-ui/index.html#model-Author
    author = deepcopy(author)

    for k in list(author.keys()):
        if k != k.lower():
            author[k.lower()] = author[k]
            del author[k]

    author.setdefault('raw', None)
    author.setdefault('affiliation', [])

    for affiliation in author['affiliation']:
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
