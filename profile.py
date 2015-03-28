import pubmed
import json
from app import my_redis
from db import make_key

def make_profile(name, pmids):
    # save the articles that go with this profile
    slug = make_slug(name)
    key = make_key("user", slug, "articles")
    my_redis.sadd(key, pmids)

    for pmid in pmids:
        # put it on the scopus queue
        # skipping this for now
        pass

    # get all the infos in one big pull from pubmed
    # this is blocking and can take lord knows how long
    medline_records = pubmed.get_medline_records(pmids)


    # save all the medline records
    for record in medline_records:
        key = make_key("article", record['PMID'], "dump")
        print "made a key: " + key
        val = json.dumps(record)
        my_redis.set(key, val)



    for record in medline_records:
        # put it in the refset queue
        pass

    return medline_records


def make_slug(name):
    titled = name.title()
    slug = ''.join(e for e in titled if e.isalnum())
    return slug



def get_profile(slug):
    return "got the profile " + slug