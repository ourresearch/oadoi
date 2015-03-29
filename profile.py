import pubmed
import json
from app import my_redis
from db import make_key
import article
from refset import enqueue_for_refset

def make_profile(name, pmids):
    # save the articles that go with this profile
    slug = make_slug(name)
    key = make_key("user", slug, "articles")
    my_redis.sadd(key, *pmids)



    # get all the infos in one big pull from pubmed
    # this is blocking and can take lord knows how long
    medline_records = pubmed.get_medline_records(pmids)


    # save all the medline records
    for record in medline_records:
        key = make_key("article", record['PMID'], "dump")
        val = json.dumps(record)
        my_redis.set(key, val)

    # put everything on the refset queue
    for record in medline_records:
        enqueue_for_refset(record)

    return medline_records


def make_slug(name):
    titled = name.title()
    slug = ''.join(e for e in titled if e.isalnum())
    return slug



def get_profile(slug):
    key = make_key("user", slug, "articles")
    pmid_list = my_redis.smembers(key)

    if not pmid_list:
        ret = None

    else:
        my_articles_list = article.get_article_set(pmid_list)
        ret = {
            "slug": slug,
            "articles": [a.to_dict() for a in my_articles_list]
        }

    return ret