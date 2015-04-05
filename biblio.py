from util import dict_from_dir


def explode_mesh_line(mesh_line):
    # turn foo/bar/*baz into a list of ['foo/bar', 'foo/*baz']

    terms = mesh_line.split("/")
    ret = []
    if len(terms) == 1:
        ret.append(terms[0])
    else:
        ret = []
        for qualifier in terms[1:]:
            ret.append(terms[0] + "/" + qualifier)

    return ret

def explode_all_mesh(mesh_lines_list):
    ret = []
    for mesh_line in mesh_lines_list:
        exploded_line = explode_mesh_line(mesh_line)
        ret += exploded_line

    return ret


class Biblio(object):

    def __init__(self, medline_citation):
        self.medline_citation = medline_citation

    @property
    def pmid(self):
        return self.medline_citation.get("PMID", "")

    @property
    def title(self):
        try:
            return self.medline_citation["TI"]
        except KeyError:
            return self.medline_citation.get("BTI", "")


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
            return self.medline_citation["DP"][0:4]
        except KeyError:
            return ""

    @property
    def mesh_terms(self):
        try:
            terms = explode_all_mesh(self.medline_citation["MH"])
            return terms
        except KeyError:
            return []

    @property
    def mesh_terms_no_stars(self):
        return [mesh.replace("*", "") for mesh in self.mesh_terms]

    @property
    def mesh_terms_no_qualifiers(self):
        main_terms_set = set()
        for full_mesh_term in self.mesh_terms_no_stars:
            main_term = full_mesh_term.split("/")[0]
            main_terms_set.add(main_term)
        return list(main_terms_set)


    def __repr__(self):
        return "<Biblio {pmid}>".format(
            pmid=self.pmid)

    def to_dict(self, hide_keys=[], show_keys="all"):
        hide_keys += [
            "medline_citation",
            "mesh_terms_no_stars",
            "mesh_terms_no_qualifiers"
            ]
        ret = dict_from_dir(self, hide_keys, show_keys)
        return ret

