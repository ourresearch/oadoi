from biblio import Biblio

from Bio import Entrez
from Bio import Medline
from collections import defaultdict
import os
import arrow

# module setup stuff
Entrez.email = "team@impactstory.org"
Entrez.tool = "Impactstory"


def get_medline_records(pmids):
    handle = Entrez.efetch(db="pubmed", id=pmids, rettype="medline", retmode="text")
    records = Medline.parse(handle)
    return list(records)


def get_pmids_in_date_window(center_date, core_journals):

    search_string = '(English[lang] NOT Review[ptyp] AND "journal article"[ptyp])'

    search_string += ' AND ('
    journal_subterms = ['"{}"[journal]'.format(journal) for journal in core_journals]
    search_string += ' OR '.join(journal_subterms)
    search_string += ')'

    center_date_arrow = arrow.get(center_date)
    start_date_arrow = center_date_arrow.replace(months=-3)
    end_date_arrow = center_date_arrow.replace(months=+3)

    search_string += ' AND "{start_date}":"{end_date}"[PDAT] '.format(
        start_date=start_date_arrow.format("YYYY/MM/DD"),
        end_date=end_date_arrow.format("YYYY/MM/DD"))

    print "searching pubmed for ", search_string

    handle = Entrez.esearch(
        db="pubmed",
        term=search_string, 
        retmax=10000  #max        
        )
    record = Entrez.read(handle)
    # print "found this on pubmed:", record["IdList"]
    pmids = record["IdList"]

    return pmids











######
# Not used anymore

def get_pmids_for_refset_using_mesh(mesh_terms, year):
    search_string = '({first_mesh_term}[mesh] AND {second_mesh_term}[mesh]) '\
        ' AND ("{year}"[Date - Publication])' \
        ' AND (English[lang] NOT Review[ptyp] AND "journal article"[ptyp])'.format(
        first_mesh_term=mesh_terms[0],
        second_mesh_term=mesh_terms[1],
        year=year
    )

    print "searching pubmed for ", search_string

    # add one because we'll remove the article itself, later
    RETMAX = int(os.getenv("REFSET_LENGTH", 50)) + 1

    handle = Entrez.esearch(
        db="pubmed",
        term=search_string,
        retmax=RETMAX)
    record = Entrez.read(handle)
    print "found this on pubmed:", record["IdList"]
    return record["IdList"]


def get_related_pmids(pmids):
    # send just first few pmids, otherwise URL gets too long
    if len(pmids) > 50:
        pmids = pmids[0:50]
    # send pmids as a list of strings, not a single string, to get
    # elink call that has ids send individually
    # see https://github.com/biopython/biopython/issues/361
    # pmids_list = [str(pmid) for pmid in pmids]
    pmids_string = ",".join([str(pmid) for pmid in pmids])
    record = Entrez.read(Entrez.elink(dbfrom="pubmed", id=pmids_string))
    # print record
    related_pmids = [entry["Id"] for entry in record[0]["LinkSetDb"][0]["Link"]]
    return related_pmids


def get_second_order_related(pmid):
    related_pmids = get_related_pmids([pmid])
    print "first 10 related pmids for pmid", pmid, related_pmids[0:10]
    if not related_pmids:
        return []
    second_order_related_pmids = get_related_pmids(related_pmids)
    print "first 10 second-order related pmids for pmid", pmid, second_order_related_pmids[0:10]

    return second_order_related_pmids


def get_filtered(pmids, year=None, mesh_terms=[]):
    if not pmids:
        return []

    pmids_string = ",".join([str(pmid) for pmid in pmids])
    handle = Entrez.epost(db="pubmed", id=pmids_string)
    result = Entrez.read(handle)
    handle.close()

    webenv = result["WebEnv"]
    query_key = result["QueryKey"]

    search_string = ""
    for mesh_term in mesh_terms:
        search_string += '" {mesh_term}"[mesh] '.format(
            mesh_term=mesh_term)

    if year:
        search_string += '" {year}"[Date - Publication] '.format(
            year=year)

    # add one because we'll remove the article itself, later
    RETMAX = int(os.getenv("REFSET_LENGTH", 50)) + 1

    print "searching pubmed for ", search_string

    handle = Entrez.esearch(
        db="pubmed",
        term=search_string,
        retmax=RETMAX,
        webenv=webenv, 
        query_key=query_key)
    record = Entrez.read(handle)
    handle.close()

    print "found this on pubmed:", record["IdList"]

    return record["IdList"]


def get_results_from_author_name(author_name):
    handle = Entrez.esearch(db="pubmed", term=author_name)
    result = Entrez.read(handle)
    handle.close()
    print result
    return result


def get_pmids_from_author_name(author_name):
    result = get_results_from_author_name(author_name)
    return result["IdList"]

def mesh_histogram(biblios):
    mesh_hide_terms = [
        "Humans",
        "Female",
        "Male",
        "Animals",
        "Mice",
        "Aged",
        "Adult",
        "Middle Aged"
    ]

    mesh_histogram = defaultdict(int)
    for biblio in biblios:
        for mesh in biblio.mesh_terms_no_qualifiers:
            if mesh not in mesh_hide_terms:                
                mesh_histogram[mesh] += 1
    return mesh_histogram


# only being used in the exploring views endpoints right now
def mesh_hist_to_list(mesh_histogram):
    mesh_hist_list = [(count, mesh) for (mesh, count) in mesh_histogram.iteritems()]
    sorted_mesh_hist_list = sorted(mesh_hist_list, reverse=True)
    response = []

    for (count, mesh) in sorted_mesh_hist_list:
        filled_count = str(count).rjust(10, " ")
        pretty_string = "{}: {}".format(filled_count, mesh)
        response.append(pretty_string)

    return response

