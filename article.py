import json
from biblio import Biblio
from app import my_redis
from db import make_key
import pubmed

class Article(object):

    def __init__(self, pmid, biblio, raw_refset_dict):
        self.pmid = pmid
        self.biblio = biblio
        self.raw_refset_dict = raw_refset_dict


    @property
    def percentile(self):
        refset_citations = self.refset_dict.values()
        if not refset_citations or "None" in refset_citations:
            return None

        if "None"==self.citations:
            return None

        refset_length = len(refset_citations)
        print refset_length, refset_citations
        greater_equal_count = sum([self.citations>=c for c in refset_citations])
        print greater_equal_count
        percentile = int(round(100.0*greater_equal_count / refset_length, 0))
        return percentile
        

    @property
    def biblio_dict(self):
        return json.loads(self.biblio)

    @property
    def citations(self):
        try:
            return self.raw_refset_dict[self.pmid]
        except KeyError:
            return None

    @property
    def title(self):
        return self.biblio_dict["TI"]


    @property
    def refset_dict(self):
        """
        We're hackily putting the citations to this article in its own
        refset. No one using this will expect that, so remove it here.
        """
        ret = {}
        for pmid, citations in self.raw_refset_dict.iteritems():
            if pmid != self.pmid:
                ret[pmid] = citations
        return ret

    def to_dict(self, hide_keys=[], show_keys="all"):
        return {
            "pmid": self.pmid,
            "biblio": self.biblio.to_dict(hide_keys=hide_keys, show_keys=show_keys),
            "refset": self.refset_dict,
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

    pipe = my_redis.pipeline()
    for pmid in pmid_list:
        key = make_key("article", pmid, "refset")
        pipe.hgetall(key)

    refset_dicts = pipe.execute()

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



