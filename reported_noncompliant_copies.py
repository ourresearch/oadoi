from util import clean_doi

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
        lookup_normalized[clean_doi(doi_key)] = [noncompliant_url_fragment.lower() for noncompliant_url_fragment in fragment_list]

    return lookup_normalized.get(clean_doi(dirty_doi), [])
