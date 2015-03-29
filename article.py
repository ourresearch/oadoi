import json
from app import my_redis
from db import make_key
import pubmed

class Article(object):

    def __init__(self, pmid, medline_dump, raw_refset_dict):
        self.pmid = pmid
        self.medline_dump = medline_dump
        self.raw_refset_dict = raw_refset_dict


    @property
    def percentile(self):
        return 42

    @property
    def biblio_dict(self):
        return json.loads(self.medline_dump)

    @property
    def short_biblio_dict(self):
        return trim_medline_citation(self.biblio_dict)

    @property
    def citations(self):
        return self.raw_refset_dict[self.pmid]

    @property
    def title(self):
        return self.biblio_dict["TI"]


    @property
    def refset_dict(self):
        """
        We're hackily putting the citations to this article in its own
        refset. No one using this will expect that, so remove it here.
        """
        return self.raw_refset_dict
        ret = {}
        for pmid, citations in self.raw_refset_dict.iteritems():
            if pmid != self.pmid:
                ret[pmid] = citations
        return ret

    def to_dict(self):
        return {
            "pmid": self.pmid,
            "biblio": self.short_biblio_dict,
            "refset": self.refset_dict,
            "citations": self.citations,
            "percentile": self.percentile
        }



def trim_medline_citation(record):
    return {
        "title": record["TI"],
        "mesh_terms": pubmed.explode_all_mesh(record["MH"]),
        "year": record["CRDT"][0][0:4],
        "pmid": record["PMID"]
    }


def get_article_set(pmid_list):


    # first get the article biblio dicts
    pipe = my_redis.pipeline()
    for pmid in pmid_list:
        key = make_key("article", pmid, "dump")
        pipe.get(key)
    medline_dumps = pipe.execute()

    pipe = my_redis.pipeline()
    for pmid in pmid_list:
        key = make_key("article", pmid, "refset")
        pipe.hgetall(key)

    refset_dicts = pipe.execute()

    article_arg_tuples = zip(pmid_list, medline_dumps, refset_dicts)

    article_objects = []
    for choople in article_arg_tuples:
        my_article = Article(
            choople[0],  # pmid
            choople[1],  # medline_dump
            choople[2]   # refset dict
        )
        article_objects.append(my_article)

    return article_objects



