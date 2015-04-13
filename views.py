from app import app
from scopus import get_scopus_citations_for_pmids
from pubmed import get_pmids_from_author_name
from profile import make_profile
from profile import get_profile
from article import get_article_set
from journal import filter_journal_list

from flask import make_response
from flask import request
from flask import abort
from flask import render_template
import os
import json
from time import sleep



def json_resp_from_thing(thing):
    json_str = json.dumps(thing, sort_keys=True, indent=4)
    resp = make_response(json_str, 200)
    resp.mimetype = "application/json"
    return resp


def abort_json(status_code, msg):
    body_dict = {
        "HTTP_status_code": status_code,
        "message": msg,
        "error": True
    }
    resp_string = json.dumps(body_dict, sort_keys=True, indent=4)
    resp = make_response(resp_string, status_code)
    resp.mimetype = "application/json"
    abort(resp)


@app.route("/<path:page>")  # from http://stackoverflow.com/a/14023930/226013
@app.route("/")
def index_view(path="index", page=""):
    return render_template('index.html')




@app.route("/profile", methods=["POST"])
def create_profile():
    pmids = [str(pmid) for pmid in request.json["pmids"] ]
    name = request.json["name"]
    core_journals = request.json["core_journals"]
    medline_records = make_profile(name, pmids, core_journals)
    return json_resp_from_thing(medline_records)

@app.route("/make-profile/<name>/<pmids_str>/<core_journals_str>")
def profile_create_tester(name, pmids_str,core_journals_str):
    medline_records = make_profile(
            name, 
            pmids_str.split(","),
            core_journals_str.split(","),
            )
    return json_resp_from_thing(medline_records)



@app.route("/profile/<slug>")
def endpoint_to_get_profile(slug):
    profile = get_profile(slug)
    if profile is not None:
        return json_resp_from_thing(profile)
    else:
        abort_json(404, "this profile doesn't exist")


@app.route("/api/article/<pmid>")
def article_details(pmid):
    article = None

    try:
        article = get_article_set([pmid])[0]
    except (KeyError, TypeError):
        pass

    if article is not None:
        return json_resp_from_thing(article.to_dict())
    else:
        abort_json(404, "this article doesn't exist")



@app.route("/api/journals/<name_starts_with>")
def journals_route(name_starts_with):
    response = filter_journal_list(name_starts_with)
    return json_resp_from_thing(response)


######################################
# for admin tasks

@app.route("/api/admin/journals/all")
def journal_admin_all():
    import journal 
    journals_list = journal.create_journals_lookup_from_medline_dump()

    return json_resp_from_thing(journals_list)




######################################
# for experimenting

from pubmed import get_medline_records
from pubmed import get_filtered
from pubmed import get_related_pmids
import pubmed
from refset import build_refset
from biblio import Biblio
from collections import defaultdict
from refset import get_pmids_for_refset

@app.route("/api/refset/<date>/<core_journals_str>/<refset_size>")
def refset_experimenting(date, core_journals_str, refset_size):
    core_journals = core_journals_str.split(",")
    pmids = get_pmids_for_refset(date, core_journals, int(refset_size))
    # return json_resp_from_thing(pmids)
    # return json_resp_from_thing(",".join(pmids))

    print "HI HEATHER"
    print "len pmids", len(pmids)
    raw_refset_dict = dict((pmid, None) for pmid in pmids)
    refset = build_refset(raw_refset_dict)
    return json_resp_from_thing(refset.to_dict())


@app.route("/api/related/<pmid>")
def related_pmid(pmid):
    related_pmids = get_related_pmids([pmid])
    record = get_medline_records([pmid])
    year = Biblio(record[0]).year
    pmids = get_filtered(related_pmids, year=year)

    raw_refset_dict = dict((pmid, None) for pmid in pmids)
    refset_details = build_refset(raw_refset_dict)
    return json_resp_from_thing(refset_details.to_dict())


@app.route("/api/playing/<pmid>")
def refset(pmid):
    record = get_medline_records([pmid])
    owner_biblio = Biblio(record[0])


    related_pmids = get_related_pmids([pmid])

    related_records = get_medline_records(related_pmids)
    related_biblios = [Biblio(record) for record in related_records]

    top_10_mesh_hist = pubmed.mesh_histogram(related_biblios[0:50])
    sorted_top_10 = pubmed.mesh_hist_to_list(top_10_mesh_hist)

    all_mesh_hist = pubmed.mesh_histogram(related_biblios)
    sorted_all = pubmed.mesh_hist_to_list(all_mesh_hist)

    response = {
        "owner_mesh": owner_biblio.mesh_terms,
        "top_10_mesh_histogram": sorted_top_10,
        "all_mesh_histogram": sorted_all
    }

    return json_resp_from_thing(response)





@app.route("/api/author/<author_name>/pmids")
def author_pmids(author_name):
    pmids = get_pmids_from_author_name(author_name)
    return json_resp_from_thing(pmids)

@app.route("/api/author/<author_name>/scopus")
def author_scopus(author_name):
    pmids = get_pmids_from_author_name(author_name)
    citations = get_scopus_citations_for_pmids(pmids)
    return json_resp_from_thing(citations)

@app.route("/api/pmids/<pmids_string>/scopus")
def pmids_scopus(pmids_string):
    pmids = pmids_string.split(",")
    response = get_scopus_citations_for_pmids(pmids)
    return json_resp_from_thing(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5008))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
