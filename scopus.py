import os
import sys
import requests
import time
import db
import logging
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

# set up logging
# see http://wiki.pylonshq.com/display/pylonscookbook/Alternative+logging+configuration
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='[%(process)3d] %(levelname)8s %(threadName)30s %(name)s - %(message)s'
)
logger = logging.getLogger("scopus")


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

    logger.info("saving scopus count of {count} to pmid {pmid} in {key}".format(
        count=citation_count,
        pmid=refset_member_pmid,
        key=key
    ))



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


    logger.info("LIVE GET of scopus with {}".format(url))

    headers = {}
    headers["accept"] = "application/json"
    timeout_seconds = 30
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
                logger.info(response)
            except (KeyError, ValueError):
                # not in Scopus database
                response = "error: couldn't parse response"
    return response



