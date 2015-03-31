
class Biblio(object):

    def __init__(self, medline_citation):
        self.medline_citation = medline_citation


    def title(self):
        return self.medline_citation["TI"]

    def author_string(self):
        return ", ".join(self.medline_citation["AU"])

    def abstract(self):
        return self.medline_citation["AB"]