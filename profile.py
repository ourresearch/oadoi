import pubmed
import json
from app import my_redis
from app import scopus_queue
from db import make_key
from scopus import enqueue_scopus
import article

def make_profile(name, pmids):
    # save the articles that go with this profile
    slug = make_slug(name)
    key = make_key("user", slug, "articles")
    my_redis.sadd(key, *pmids)

    #for pmid in pmids:
    #    enqueue_scopus(pmid)


    # get all the infos in one big pull from pubmed
    # this is blocking and can take lord knows how long
    medline_records = pubmed.get_medline_records(pmids)


    # save all the medline records
    for record in medline_records:
        key = make_key("article", record['PMID'])
        print "made a key: " + key
        val = json.dumps(record)
        my_redis.hset(key, "medline_dump", val)



    for record in medline_records:
        # put it in the refset queue
        pass

    return medline_records


def make_slug(name):
    titled = name.title()
    slug = ''.join(e for e in titled if e.isalnum())
    return slug



def get_profile(slug):
    key = make_key("user", slug, "articles")
    pmid_list = my_redis.smembers(key)
    my_articles_list = article.get_article_set(pmid_list)

    print "my_articles_list"
    print my_articles_list

    ret = {
        "slug": slug,
        "articles": [a.to_dict() for a in my_articles_list]
    }

    return ret