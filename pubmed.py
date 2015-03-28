from Bio import Entrez
from Bio import Medline

# module setup stuff
Entrez.email = "team@impactstory.org"




def get_medline_records(pmids):
    handle = Entrez.efetch(db="pubmed", id=pmids, rettype="medline", retmode="text")
    records = Medline.parse(handle)
    return list(records)




def get_results_from_author_name(author_name):
    handle = Entrez.esearch(db="pubmed", term=author_name)
    result = Entrez.read(handle)
    handle.close()
    print result
    return result

def get_pmids_from_author_name(author_name):
    result = get_results_from_author_name(author_name)
    return result["IdList"]

