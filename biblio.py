from pubmed import explode_all_mesh
from util import dict_from_dir

class Biblio(object):

    def __init__(self, medline_citation):
        self.medline_citation = medline_citation

    @property
    def pmid(self):
        return self.medline_citation.get("PMID", "")

    @property
    def title(self):
        return self.medline_citation.get("TI", "")

    @property
    def author_string(self):
        authors = self.medline_citation.get("AU", [])
        return ", ".join(authors)

    @property
    def abstract(self):
        return self.medline_citation.get("AB", "")

    @property
    def journal(self):
        return self.medline_citation.get("JT", "")

    @property
    def year(self):
        try:
            return self.medline_citation["CRDT"][0][0:4]
        except KeyError:
            return ""

    @property
    def mesh_terms(self):
        try:
            terms = explode_all_mesh(self.medline_citation["MH"])
            return terms
        except KeyError:
            return []

    def __repr__(self):
        return "<Biblio {pmid}>".format(
            pmid=self.pmid)

    def to_dict(self, hide_keys=[], show_keys="all"):
        hide_keys.append("medline_citation")
        ret = dict_from_dir(self, hide_keys, show_keys)
        return ret

