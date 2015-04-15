import pubmed
from biblio import Biblio
import db
from app import refset_queue
from app import my_redis
from scopus import enqueue_scopus

from collections import defaultdict
import arrow
import os
from journals_histogram import make_journals_histogram


def enqueue_for_refset(medline_citation, core_journals):
    biblio = Biblio(medline_citation)
    show_keys = [
        "pmid",
        "doi",
        "best_pub_date",
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


def get_closest_biblios(possible_biblios, center_date, refset_size):
    sorted_biblios = sorted(
                        possible_biblios, 
                        key=lambda biblio: abs(biblio.pseudo_published_days_since(center_date)))
    picked_biblios = sorted_biblios[0:min(refset_size, len(sorted_biblios))]
    return picked_biblios

def tabulate_non_epub_biblios_by_pub_date(biblios):
    biblios_by_pub_date = defaultdict(list)
    for biblio in biblios:
        # don't set pseudo dates for things with epub dates
        if not biblio.has_epub_date:
            biblios_by_pub_date[biblio.pub_date].append(biblio)
    return biblios_by_pub_date

def timedelta_between(date1, date2):
    date1_arrow = arrow.get(date1)
    date2_arrow = arrow.get(date2)
    response = date1_arrow - date2_arrow
    return response

def set_pseudo_dates(biblios):
    # initialize
    for biblio in biblios:
        biblio.pseudo_date = biblio.best_pub_date

    response_biblios = dict((biblio.pmid, biblio) for biblio in biblios)
    biblios_by_pub_date = tabulate_non_epub_biblios_by_pub_date(biblios)

    # if there are some publications without epub dates
    if biblios_by_pub_date:
        sorted_pub_dates = sorted(biblios_by_pub_date.keys())
        previous_pub_dates = [sorted_pub_dates[0]] + sorted_pub_dates[:-1]
        previous_pub_date_lookup = dict(zip(sorted_pub_dates, previous_pub_dates))

        for (real_pub_date, biblio_list) in biblios_by_pub_date.iteritems():
            num_pubs_on_this_date = len(biblio_list)
            previous_pub_date = previous_pub_date_lookup[real_pub_date]
            timedelta_since_last_pub_date = timedelta_between(real_pub_date, previous_pub_date)
            pseudo_timedelta_step_size = timedelta_since_last_pub_date / num_pubs_on_this_date

            for (i, biblio) in enumerate(biblio_list):        
                timedelta_to_add = i * pseudo_timedelta_step_size
                biblio.add_to_pseudo_date(timedelta_to_add)
                response_biblios[biblio.pmid] = biblio

    return response_biblios.values()


def get_pmids_for_refset(refset_center_date, core_journals, refset_size=None):
    if not refset_size:
        refset_size = int(os.getenv("REFSET_LENGTH", 50))

    possible_pmids = pubmed.get_pmids_in_date_window(refset_center_date, core_journals)
    possible_records = pubmed.get_medline_records(possible_pmids)
    possible_biblios = [Biblio(record) for record in possible_records]
    pseudo_date_biblios = set_pseudo_dates(possible_biblios)

    refset_biblios = get_closest_biblios(
        pseudo_date_biblios, 
        refset_center_date, 
        refset_size)
    refset_pmids = [biblio.pmid for biblio in refset_biblios]
    return refset_pmids
     

def make_refset(biblio_dict, core_journals):
    refset_owner_pmid = biblio_dict["pmid"]
    refset_owner_doi = biblio_dict["doi"]
    refset_center_date = biblio_dict["best_pub_date"]

    print "making a refset for {pmid}".format(pmid=refset_owner_pmid)

    refset_pmids = get_pmids_for_refset(refset_center_date, core_journals)

    # put our article of interest in its own refset
    refset_pmids.append(refset_owner_pmid)

    print refset_pmids

    # store the newly-minted refset. scopus will save citations
    # to it as it finds them.  Do this before putting on scopus queue.
    save_new_refset(refset_pmids, refset_owner_pmid)

    # now let's get scopus looking for citations on this refset's members
    for pmid_in_refset in refset_pmids:
        enqueue_scopus(pmid_in_refset, refset_owner_pmid, refset_owner_doi)




def save_new_refset(refset_pmids, pmid_we_are_making_refset_for):
    key = db.make_refset_key(pmid_we_are_making_refset_for)

    refset_dict = {}
    for pmid in refset_pmids:
        refset_dict[pmid] = None

    print "saving this refset", key, refset_dict
    my_redis.hmset(key, refset_dict)


def get_refsets(pmid_list):
    pipe = my_redis.pipeline()
    for pmid in pmid_list:
        key = db.make_refset_key(pmid)
        pipe.hgetall(key)

    refset_dicts = pipe.execute()
    return refset_dicts  


def build_refset(raw_refset_dict):
    refset = Refset(raw_refset_dict)
    refset.biblios = refset.get_biblios_from_medline()
    return refset


def build_refset_from_records(records):
    raw_refset_dict = dict([(record[pmid], None) for record in records])
    refset = Refset(raw_refset_dict)
    refset.biblios = refset.get_biblios_from_medline(records)
    return refset


class Refset(object):

    def __init__(self, raw_refset_dict):
        self.raw_refset_dict = raw_refset_dict
        self.biblios = {}

    @property
    def pmids(self):
        return self.raw_refset_dict.keys()

    # not a property, because it does a network call
    def get_biblios_from_medline(self):
        records = pubmed.get_medline_records(self.pmids)
        biblios = self.get_biblios_from_medline_records(records)
        return biblios

    def get_biblios_from_medline_records(self, medline_records):
        biblios = {}
        for record in medline_records:
            biblio = Biblio(record)
            biblios[biblio.pmid] = biblio
        return biblios


    @property
    def refset_length(self):
        return len(self.pmids)

    @property
    def scopus_max(self):
        scopus_values = self.raw_refset_dict.values()
        scopus_values_int = [s for s in scopus_values if isinstance(s, int)]
        try:
            response = max(scopus_values_int)
        except ValueError:
            response = None
        return response

    @property
    def article_details(self):
        response = {}

        for pmid in self.pmids:
            my_scopus = self.raw_refset_dict[pmid]
            try:
                scopus_scaling_factor = float(my_scopus) / float(self.scopus_max)
            except (ValueError, TypeError, ZeroDivisionError):
                # there's no scopus value
                scopus_scaling_factor = None

            response[pmid] = {
                "scopus": my_scopus,
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
        ret = make_journals_histogram(self.article_details.values())
        return ret


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


    def to_dict(self):
        return {
            "articles": self.article_details,
            "scopus_max": self.scopus_max,
            "journal_histograms": self.journal_histograms.to_dict(),
            # "mesh_summary": self.mesh_summary,
            "refset_length": self.refset_length,
            "citation_summary": self.citation_summary
        }



