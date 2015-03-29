import json
from app import my_redis
from db import make_key

class Article(object):

    def __init__(self, pmid, medline_dump, refset_dict):
        self.pmid = pmid
        self.medline_dump = medline_dump
        self.refset_dict = refset_dict


    @property
    def percentile(self):
        return 42

    @property
    def biblio_dict(self):
        return json.loads(self.medline_dump)

    def to_dict(self):
        return {
            "pmid": self.pmid,
            "biblio_dict": self.biblio_dict,
            "refset_dict": self.refset_dict,
            "percentile": self.percentile
        }





def get_article_set(pmid_list):

    print "getting these pmids: ", pmid_list

    # first get the article biblio dicts
    pipe = my_redis.pipeline()
    for pmid in pmid_list:
        key = make_key("article", pmid, "dump")
        pipe.get(key)
    medline_dumps = pipe.execute()

    print "ok got the medline dumps"
    print medline_dumps

    #pipe = my_redis.pipeline()
    #for pmid in pmid_list:
    #    key = make_key("article", pmid, "refset")
    #    pipe.get(key)
    #
    #refset_dicts = pipe.execute()

    refset_dicts = medline_dumps  # temp for testing

    article_arg_tuples = zip(pmid_list, medline_dumps, refset_dicts)
    print article_arg_tuples

    article_objects = []
    for choople in article_arg_tuples:
        my_article = Article(
            choople[0],  # pmid
            choople[1],  # medline_dump
            choople[2]   # refset dict
        )
        article_objects.append(my_article)

    return article_objects



