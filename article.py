import json
from biblio import Biblio
from app import my_redis
from db import make_key
import pubmed
from refset import build_refset
from refset import get_refsets

def is_valid_citation_count(citation_value):
    return type(citation_value) == int


class Article(object):

    def __init__(self, pmid, biblio, raw_refset_dict):
        self.pmid = pmid
        self.biblio = biblio
        self.raw_refset_dict = raw_refset_dict


    @property
    def is_old_enough_for_percentile(self):
        is_old_enough = int(biblio.year) < 2014
        return is_old_enough

    @property
    def is_calculating_percentile(self):
        is_calculating = False

        # abort if don't have own citations yet
        if "None"==self.citations:
            is_calculating = True

        # abort if refset still going through scopus
        refset_citations = self.refset_dict.values()
        if not refset_citations or "None" in refset_citations:
            is_calculating = True

        return is_calculating



    @property
    def percentile(self):

        if self.is_calculating_percentile:
            return None

        # for now, ignore refset entries that are error strings
        refset_citations = self.refset_dict.values()
        refset_citations = [c for c in refset_citations if is_valid_citation_count(c)]

        refset_length = len(refset_citations)
        greater_equal_count = sum([self.citations>=c for c in refset_citations])

        if refset_length==0:
            return None

        percentile = int(round(100.0*greater_equal_count / refset_length, 0))

        if percentile == 100:
            percentile = 99

        return percentile
        

    @property
    def biblio_dict(self):
        return json.loads(self.biblio)

    @property
    def citations(self):
        try:
            return int(self.raw_refset_dict[self.pmid])
        except (KeyError, ValueError):
            return None

    @property
    def title(self):
        return biblio.title


    @property
    def refset_dict(self):
        """
        We're hackily putting the citations to this article in its own
        refset. No one using this will expect that, so remove it here.
        """
        ret = {}
        for pmid, citations in self.raw_refset_dict.iteritems():
            if pmid != self.pmid:
                try:
                    ret[pmid] = int(citations)
                except ValueError:
                    # just put it in directly, because is error string
                    ret[pmid] = citations

        return ret

    def dict_for_profile(self):
        hide_keys = [
            "mesh_terms",
            "abstract"
        ]
        return {
            "pmid": self.pmid,
            "biblio": self.biblio.to_dict(hide_keys=hide_keys),
            "refset": self.refset_dict,
            "citations": self.citations,
            "percentile": self.percentile
        }        

    def to_dict(self, hide_keys=[], show_keys="all"):
        refset_details = build_refset(self.refset_dict)
        return {
            "pmid": self.pmid,
            "biblio": self.biblio.to_dict(hide_keys=hide_keys, show_keys=show_keys),
            "refset": refset_details.to_dict(),
            "citations": self.citations,
            "percentile": self.percentile
        }



def get_article_set(pmid_list):

    # first get the article biblio dicts
    pipe = my_redis.pipeline()
    for pmid in pmid_list:
        key = make_key("article", pmid, "dump")
        pipe.get(key)
    medline_dumps = pipe.execute()
    biblios = [Biblio(json.loads(medline_dump)) for medline_dump in medline_dumps]

    refset_dicts = get_refsets(pmid_list)

    article_arg_tuples = zip(pmid_list, biblios, refset_dicts)

    article_objects = []
    for choople in article_arg_tuples:
        my_article = Article(
            choople[0],  # pmid
            choople[1],  # biblio
            choople[2]   # refset dict
        )
        article_objects.append(my_article)

    return article_objects



