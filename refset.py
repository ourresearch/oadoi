import pubmed
from biblio import Biblio
import db
from app import refset_queue
from app import my_redis
from scopus import enqueue_scopus
import article

from collections import defaultdict


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
    print refset_pmids


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

    # just pick one at random for now, get smarter later
    major_headings = [mh for mh in biblio_dict["mesh_terms"] if "*" in mh]
    if major_headings:
        mesh_term_to_search_on = major_headings[0]
    else:
        mesh_term_to_search_on = []

    return pubmed.get_pmids_for_refset(
        biblio_dict["pmid"],
        mesh_term_to_search_on,
        biblio_dict["year"]
    )


class RefsetDetails(object):

    def __init__(self, raw_refset_dict):
        self.raw_refset_dict = raw_refset_dict

    @property
    def article_details(self):
        pmids = self.raw_refset_dict.keys()
        response = {}
        for pmid in pmids:
            response[pmid] = {
                "scopus": self.raw_refset_dict[pmid], 
                "biblio": Biblio({
                    "PMID": pmid,
                    "TI": "A fake title",
                    "JT": "Journal Of Articles",
                    "CRDT": ["2014"],
                    "AB": "About things.",
                    "MH": ["Bibliometrics"],
                    "AU": ["Kent", "Stark"]
                    }).to_dict()
            }
        return response

    @property
    def citation_summary(self):
        citation_list = self.raw_refset_dict.values()
        if "None" in citation_list:
            return None

        summary = defaultdict(int)
        for citation_count in citation_list:
            summary[citation_count] += 1

        return summary


    def to_dict(self, hide_keys=[], show_keys="all"):
        return {
            "articles": self.article_details,
            "mesh_summary": [],
            "citation_summary": self.citation_summary
        }



