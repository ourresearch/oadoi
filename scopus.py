import os
import requests
import time
import db
from rq import Queue
from rq import Connection
from rq.job import Job

from rq_worker import redis_rq_conn
from app import scopus_queue
from app import my_redis

url_template_with_doi = "https://api.elsevier.com/content/search/index:SCOPUS?query=PMID({pmid})%20OR%20DOI({doi})&field=citedby-count&apiKey={scopus_key}&insttoken={scopus_insttoken}"
url_template_no_doi = "https://api.elsevier.com/content/search/index:SCOPUS?query=PMID({pmid})&field=citedby-count&apiKey={scopus_key}&insttoken={scopus_insttoken}"
scopus_insttoken = os.environ["SCOPUS_INSTTOKEN"]
scopus_key = os.environ["SCOPUS_KEY"]



def enqueue_scopus(pmid, owner_pmid, owner_doi):

    job = scopus_queue.enqueue_call(
        func=save_scopus_citations,
        args=(pmid, owner_pmid, owner_doi),
        result_ttl=120  # number of seconds
    )
    job.meta["pmid"] = pmid
    job.meta["is_in_refset_for"] = owner_pmid
    job.save()



def save_scopus_citations(refset_member_pmid, refset_owner_pmid, refset_owner_doi):
    citation_count = get_scopus_citations(refset_member_pmid, refset_owner_doi)
    key = db.make_refset_key(refset_owner_pmid)

    my_redis.hset(key, refset_member_pmid, citation_count)

    print "saving scopus count of {count} to pmid {pmid} in {key}".format(
        count=citation_count,
        pmid=refset_member_pmid,
        key=key
    )



def get_scopus_citations(pmid, doi):

    # if doi:
    #     url = url_template_with_doi.format(
    #             scopus_insttoken=scopus_insttoken,
    #             scopus_key=scopus_key,
    #             pmid=pmid,
    #             doi=doi)
    # else:
    #     url = url_template_no_doi.format(
    #             scopus_insttoken=scopus_insttoken,
    #             scopus_key=scopus_key,
    #             pmid=pmid)

    url = url_template_no_doi.format(
        scopus_insttoken=scopus_insttoken,
        scopus_key=scopus_key,
        pmid=pmid)


    print "LIVE GET of scopus with", url

    headers = {}
    headers["accept"] = "application/json"
    timeout_seconds = 20
    r = requests.get(url, headers=headers, timeout=timeout_seconds)

    if r.status_code != 200:
        response = "error: status code {}".format(str(r.status_code))

    else:
        if "Result set was empty" in r.text:
            response = 0
        else:
            try:
                data = r.json()
                response = int(data["search-results"]["entry"][0]["citedby-count"])
                print response
            except (KeyError, ValueError):
                # not in Scopus database
                response = "error: couldn't parse response"
    return response



















#########################
# this is old, we may not need it no more
##########################

def get_scopus_citations_for_pmids(pmids):
    scopus_queue = Queue("scopus", connection=redis_rq_conn)  # False for debugging

    jobs = []
    for pmid in pmids:
        with Connection(redis_rq_conn):
            job = scopus_queue.enqueue_call(func=get_scopus_citations,
                    args=(pmid, ),
                    result_ttl=120  # number of seconds
                    )
            job.meta["pmid"] = pmid
            job.save()
        jobs.append(job)
    print jobs

    all_finished = False
    while not all_finished:
        time.sleep(2)
        print ".",
        still_working = False
        with Connection(redis_rq_conn):
            jobs = [Job.fetch(id=job.id) for job in jobs]
        jobs = [job for job in jobs if job]
        is_finished = [job.is_finished for job in jobs]
        print is_finished
        all_finished = all(is_finished)

    response = dict((job.meta["pmid"], job.result) for job in jobs)
    print response
    return response

# def get_scopus_citations_for_pmids(pmids):
#     response = {}
#     for pmid in pmids:
#         response[pmid] = get_scopus_citations(pmid)
#     return response
