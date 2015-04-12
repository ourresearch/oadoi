from util import dict_from_dir

import arrow

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


# abstracted to function to return None instead of throw exception
def date_to_arrow(date, parse_format):
    try:
        response = arrow.get(date, parse_format)
    except arrow.parser.ParserError:
        response = None
    return response


class Biblio(object):

    def __init__(self, medline_citation):
        self.medline_citation = medline_citation
        self.pseudo_date = self.best_pub_date  # override later

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

    def pseudo_published_days_since(self, date_since):
        arrow_date_since = arrow.get(date_since)
        my_date_since = arrow.get(self.pseudo_date)
        return my_date_since - arrow_date_since

    @property
    def best_pub_date(self):
        if self.epub_date:
            return self.epub_date
        else:
            return self.pub_date

    @property
    def has_epub_date(self):
        return self.epub_date != None

    def add_to_pseudo_date(self, timedelta_to_add):
        my_date_since = arrow.get(self.pseudo_date)
        new_date = my_date_since + timedelta_to_add
        self.pseudo_date = new_date.isoformat()

    @property
    def epub_date(self):
        try:
            epub_date_str = self.medline_citation["DEP"]
            return date_to_arrow(epub_date_str, 'YYYYMMDD').isoformat()
        except KeyError:
            return None

    @property
    def pub_date(self):
        try:
            pub_date_str = self.medline_citation["DP"]
        except KeyError:
            return None

        arrow_date = date_to_arrow(pub_date_str, 'YYYY MMM D')
        if not arrow_date:
            arrow_date = date_to_arrow(pub_date_str, 'YYYY MMM')
        if not arrow_date and len(pub_date_str)==4:
            arrow_date = date_to_arrow(pub_date_str, 'YYYY')
        if not arrow_date:                
            month_lookup = {
                "Winter": "Jan", 
                "Spring": "Apr", 
                "Summer": "Jul", 
                "Fall": "Oct"
            }
            year = pub_date_str[0:4]
            time_of_year = pub_date_str[5:].strip()
            new_pub_date_str = "{} {}".format(year, month_lookup[time_of_year])
            arrow_date = date_to_arrow(new_pub_date_str, 'YYYY MMM')

        return arrow_date.isoformat()


    @property
    def year(self):
        try:
            return self.medline_citation["DP"][0:4]
        except KeyError:
            return ""

    @property
    def publication_type(self):
        return self.medline_citation.get("PT", "")

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

