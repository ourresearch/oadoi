import pubmed
from biblio import Biblio
import db
from app import refset_queue
from app import my_redis
from scopus import enqueue_scopus
import article



def enqueue_for_refset(medline_citation):
    biblio = Biblio(medline_citation)
    show_keys = [
        "pmid",
        "mesh_terms",
        "year",
        "title"
        ]
    biblio_dict_for_queue = biblio.to_dict(show_keys=show_keys)

    job = refset_queue.enqueue_call(
        func=make_refset,
        args=(biblio_dict_for_queue, ),
        result_ttl=120  # number of seconds
    )
    job.meta["pmid"] = medline_citation["PMID"]
    job.save()



def make_refset(biblio_dict):
    refset_owner_pmid = biblio_dict["pmid"]

    print "making a refset for {pmid} using {mesh_terms}".format(
        pmid=refset_owner_pmid,
        mesh_terms=biblio_dict["mesh_terms"]
    )

    refset_pmids = get_refset_pmids(biblio_dict)

    # our article of interest goes in its own refset
    refset_pmids.append(refset_owner_pmid)


    # now let's get scopus looking for citations on this refset's members
    for pmid_in_refset in refset_pmids:
        enqueue_scopus(pmid_in_refset, refset_owner_pmid)

    # finally, store the newly-minted refset. scopus will save citations
    # to it as it finds them.
    save_new_refset(refset_pmids, refset_owner_pmid)



def save_new_refset(refset_pmids, pmid_we_are_making_refset_for):
    key = db.make_refset_key(pmid_we_are_making_refset_for)

    refset_dict = {}
    for pmid in refset_pmids:
        refset_dict[pmid] = None

    print "saving this refset", key, refset_dict
    my_redis.hmset(key, refset_dict)




def get_refset_pmids(biblio_dict):
    major_headings = [mh for mh in biblio_dict["mesh_terms"] if "*" in mh]

    # just pick one at random for now, get smarter later
    mesh_term_to_search_on = major_headings[0]

    return pubmed.get_pmids_for_refset(
        mesh_term_to_search_on,
        biblio_dict["year"]
    )

