from util import normalize_doi

lookup_raw = {
    "10.1016/j.biocon.2016.04.014": [
        "researchgate.net/profile/Arthur_Muneza/publication/301936941_Regional_variation_of_the_manifestation_prevalence_and_severity_of_giraffe_skin_disease_A_review_of_an_emerging_disease_in_wild_and_captive_giraffe_populations/links/57449ff608ae9ace8421a52f.pdf"
    ],
    "10.1016/j.tcb.2014.11.005": [
        "doi.org/10.6084/m9.figshare.1409475",
        "figshare.com/articles/An_open_data_ecosystem_for_cell_migration_research_/1409475",
        "doi.org/10.6084/M9.FIGSHARE.3114679",
        "figshare.com/articles/An_open_data_ecosystem_for_cell_migration_research_/3114679",
    ],
    "10.1016/j.vaccine.2014.04.085": [
        "ruvzca.sk/sites/default/files/dodatocne-subory/meta-analysis_vaccin_autism_2014.pdf"
    ],
    "10.1093/nar/gkx1020": [
        "doi.org/10.1093/nar/gkx1020"
    ],
    "10.2307/632037": [
        "pdfs.semanticscholar.org/250a/c6b55d82a496deda1d14af0174dd3ffe4b41.pdf"
    ],
    "10.1080/02640414.2017.1378494": [
      "http://libres.uncg.edu/ir/uncp/f/Effects of mild running on substantia nigra.pdf"
    ],
    "10.1145/3342428.3342662": [
        #  ticket 22288
        "http://hdl.handle.net/11693/52923",
        "https://hdl.handle.net/11511/31020",
        "https://open.metu.edu.tr/bitstream/handle/11511/31020/index.pdf",
    ]
}


def is_reported_noncompliant_url(dirty_doi, dirty_url):
    if not dirty_url:
        return False

    my_url = dirty_url.lower()
    for url_fragment in reported_noncompliant_url_fragments(dirty_doi):
        if url_fragment in my_url:
            return True
    return False


def reported_noncompliant_url_fragments(dirty_doi):
    if not dirty_doi:
        return []

    lookup_normalized = {}
    for (doi_key, fragment_list) in lookup_raw.iteritems():
        lookup_normalized[normalize_doi(doi_key)] = [noncompliant_url_fragment.lower() for noncompliant_url_fragment in fragment_list]

    return lookup_normalized.get(normalize_doi(dirty_doi), [])
