import json


class Author:
    def __init__(self, name, affiliations=None):
        if affiliations is None:
            self.affiliations = set()
            self.has_affiliations_claim = False
        else:
            self.affiliations = set(affiliations)
            self.has_affiliations_claim = True

        self.name = name

    def add_affiliation(self, affiliation):
        if not self.has_affiliations_claim:
            self.has_affiliations_claim = True

        self.affiliations.add(affiliation)

    def to_dict(self):
        return {
            'name': self.name,
            'has_affiliations_claim': self.has_affiliations_claim,
            'affiliations': list(self.affiliations)
        }

    def __str__(self):
        return json.dumps(self.to_dict(), indent=2)

    def __repr__(self):
        return f'<Author ( {self.name}, [{self.affiliations}], {self.has_affiliations_claim})>'


class AuthorAffiliations:
    def __init__(self, authors=None):
        if authors is None:
            self.authors = []
            self.has_authors_claim = False
        else:
            self.authors = authors
            self.has_authors_claim = True

    @property
    def has_affiliations_claim(self):
        return any([author.has_affiliations_claim for author in self.authors])

    def add_author(self, author):
        if not self.has_authors_claim:
            self.authors = []
            self.has_authors_claim = True

        self.authors.append(author)

    def to_dict(self):
        return {
            'authors': [author.to_dict() for author in self.authors],
            'has_authors_claim': self.has_authors_claim,
            'has_affiliations_claim': self.has_affiliations_claim
        }

    def __str__(self):
        return json.dumps(self.to_dict(), indent=2)

    def __repr__(self):
        return f'<AuthorAffiliations ( {self.authors}, {self.has_affiliations_claim})>'
