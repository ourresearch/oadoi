import pubmed
from biblio import Biblio
import db
from app import refset_queue
from app import my_redis
from scopus import enqueue_scopus

from collections import defaultdict
from itertools import chain


def enqueue_for_refset(medline_citation, core_journals):
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
        args=(biblio_dict_for_queue, core_journals),
        result_ttl=120  # number of seconds
    )
    job.meta["pmid"] = medline_citation["PMID"]
    job.save()



def make_refset(biblio_dict, core_journals):
    refset_owner_pmid = biblio_dict["pmid"]

    print "making a refset for {pmid}".format(
        pmid=refset_owner_pmid
    )

    refset_pmids = get_refset_pmids(biblio_dict, core_journals)

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




def get_refset_pmids(biblio_dict, core_journals):
    return pubmed.get_pmids_for_refset(
        biblio_dict["pmid"],
        biblio_dict["year"],
        core_journals
    )



class RefsetDetails(object):

    def __init__(self, raw_refset_dict):
        self.raw_refset_dict = raw_refset_dict
        self.biblios = {}
        records = pubmed.get_medline_records(self.pmids)
        for record in records:
            biblio = Biblio(record)
            pmid = biblio.pmid
            self.biblios[pmid] = biblio

    @property
    def pmids(self):
        return self.raw_refset_dict.keys()

    @property
    def refset_length(self):
        return len(self.pmids)

    @property
    def scopus_max(self):
        scopus_values = self.raw_refset_dict.values()
        scopus_values_int = [s for s in scopus_values if isinstance(s, int)]
        return max(scopus_values_int)

    @property
    def article_details(self):
        response = {}

        for pmid in self.pmids:
            my_scopus = self.raw_refset_dict[pmid]
            try:
                scopus_scaling_factor = float(my_scopus) / float(self.scopus_max)
            except ValueError:
                # there's no scopus value
                scopus_scaling_factor = None

            response[pmid] = {
                "scopus": my_scopus,
                "scopus_scaling_factor": scopus_scaling_factor,
                "biblio": self.biblios[pmid].to_dict(hide_keys=["abstract", "mesh_terms"])
            }

        return response

    def _make_scopus_histogram(self, articles):
        histogram_dict = defaultdict(list)
        for article in articles:
            my_scopus = article["scopus"]
            histogram_dict[my_scopus].append(article)

        return histogram_dict.values()

    @property
    def journal_histograms(self):
        journals_dict = defaultdict(list)
        for pmid, article in self.article_details.iteritems():
            journal_name = article["biblio"]["journal"]
            journals_dict[journal_name].append(article)

        journals = []
        flat_bins_list = []
        for journal_name, journal_articles in journals_dict.iteritems():
            my_scopus_bins = self._make_scopus_histogram(journal_articles)
            flat_bins_list += my_scopus_bins

            journals.append({
                "name": journal_name,
                "scopus_bins": my_scopus_bins,
                "num_articles": len(journal_articles)
            })

        return {
            "journals": journals,
            "max_bin_size": max([len(b) for b in flat_bins_list])
        }



    @property
    def citation_summary(self):
        citation_list = self.raw_refset_dict.values()
        if "None" in citation_list:
            return None

        summary = defaultdict(int)
        for citation_count in citation_list:
            summary[citation_count] += 1

        return summary

    @property
    def mesh_summary(self):
        summary = defaultdict(int)
        for (pmid, biblio) in self.biblios.iteritems():
            for mesh in biblio.mesh_terms:
                summary[mesh] += 1

        return summary


    def to_dict(self, hide_keys=[], show_keys="all"):
        return {
            "articles": self.article_details,
            "scopus_max": self.scopus_max,
            "journal_histograms": self.journal_histograms,
            "mesh_summary": self.mesh_summary,
            "refset_length": self.refset_length,
            "citation_summary": self.citation_summary
        }



