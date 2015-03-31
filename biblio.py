from pubmed import explode_all_mesh
from util import dict_from_dir

class Biblio(object):

    def __init__(self, medline_citation):
        self.medline_citation = medline_citation

    @property
    def pmid(self):
        return self.medline_citation["PMID"]

    @property
    def title(self):
        return self.medline_citation["TI"]

    @property
    def author_string(self):
        return ", ".join(self.medline_citation["AU"])

    @property
    def abstract(self):
        try:
            return self.medline_citation["AB"]
        except KeyError:
            return None

    @property
    def journal(self):
        return self.medline_citation["JT"]

    @property
    def mesh_terms(self):
        terms = explode_all_mesh(self.medline_citation["MH"])
        return terms

    def to_dict(self, hide_keys=None, show_keys="all"):
        ret = dict_from_dir(self, hide_keys, show_keys)
        return ret

