from sqlalchemy import text
from sqlalchemy import orm

from app import db
from models.package import Package
from models.package import shortcut_igraph_data_dict
from models.package import make_language
from models.pypi_package import PypiPackage
from models.pypi_package import shortcut_get_pypi_package_names
from models.cran_package import CranPackage
from models.person import Person
from models.person import add_person_leaderboard_filters
from models.contribution import Contribution
from models.github_repo_deplines import GithubRepoDeplines
from models.github_repo import GithubRepo
from models.tags import Tags
from jobs import update_registry
from jobs import Update



def get_leaders(filters, page_size=25):
    if filters["type"] in ["package", "packages"]:
        fn = get_packages
    elif filters["type"] in ["person", "people", "persons"]:
        fn = get_people
    elif filters["type"] in ["tag", "tags"]:
        fn = get_tags
    else:
        raise ValueError("you can only get person, package, or tag leaders.")

    # this can break things downstream.
    filters_without_type = {k:v for k, v in filters.iteritems() if k != "type"}
    return fn(filters=filters_without_type, page_size=page_size)


def get_tags(filters, page_size=25):
    q = Tags.query
    for k, v in filters.iteritems():

        order_by_column = Tags.count_academic.desc()

        # handle only_academic differently, is an order_by
        if k == "is_academic":
            pass
        else:
            # tags table is named a little differently        
            if k == "host":
                k = "namespace"

            attr = getattr(Tags, k)
            q = q.filter(attr==v)

    total_count = q.count()

    q = q.order_by(order_by_column)
    q = q.limit(page_size)
    objects = q.all()
    return [total_count, objects]


def get_people(filters, page_size=25):
    q = Person.query
    q = add_person_leaderboard_filters(q)
    q = q.options(
        orm.subqueryload_all(
            Person.contributions,
            Contribution.package 
        )
    )
    for k, v in filters.iteritems():
        if k == "tags":
            pass # don't do anything for these for now for people
        else:
            if k == "host":
                k = "main_language"
                v = make_language(v)

            attr = getattr(Person, k)
            q = q.filter(attr==v)

    total_count = q.count()

    q = q.filter(Person.impact != None)
    q = q.order_by(Person.impact.desc())
    q = q.limit(page_size)
    objects = q.all()
    return (total_count, objects)


def get_packages(filters, page_size=25):
    q = Package.query.options(
        orm.subqueryload_all(
            Package.contributions, 
            Contribution.person 
        )
    )
    for k, v in filters.iteritems():
        if k == "tag":
            q = q.filter(Package.tags.has_key(v))
        else:
            attr = getattr(Package, k)
            q = q.filter(attr==v)

    total_count = q.count()

    q = q.filter(Package.impact != None)
    q = q.order_by(Package.impact.desc(), Package.num_downloads.desc())
    q = q.limit(page_size)

    objects = q.all()
    return (total_count, objects)



q = db.session.query(CranPackage.id)
update_registry.register(Update(
    job=CranPackage.set_rev_deps_tree,
    query=q,
    shortcut_fn=CranPackage.shortcut_rev_deps_pairs
))

q = db.session.query(PypiPackage.id)
update_registry.register(Update(
    job=PypiPackage.set_rev_deps_tree,
    query=q,
    shortcut_fn=PypiPackage.shortcut_rev_deps_pairs
))




q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.requires_files != None)
update_registry.register(Update(
    job=PypiPackage.set_host_deps,
    query=q,
    queue_id=5
))


q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.import_name == None)
update_registry.register(Update(
    job=PypiPackage.set_import_name,
    query=q,
    queue_id=1
))






q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.requires_files == None)
update_registry.register(Update(
    job=PypiPackage.set_requires_files,
    query=q,
    queue_id=6
))



q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.api_raw == None)
update_registry.register(Update(
    job=PypiPackage.set_api_raw,
    query=q,
    queue_id=4
))


q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.setup_py == None)
update_registry.register(Update(
    job=PypiPackage.set_setup_py,
    query=q,
    queue_id=2
))


q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.setup_py != None)
q = q.filter(PypiPackage.setup_py_import_name == None)
update_registry.register(Update(
    job=PypiPackage.set_setup_py_import_name,
    query=q,
    queue_id=3
))


q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.tags == None)
update_registry.register(Update(
    job=PypiPackage.set_tags,
    query=q,
    queue_id=2
))

q = db.session.query(PypiPackage.id)  # no run marker
update_registry.register(Update(
    job=PypiPackage.set_intended_audience,
    query=q,
    queue_id=2
))

q = db.session.query(PypiPackage.id)  # no run marker
update_registry.register(Update(
    job=PypiPackage.set_is_academic,
    query=q,
    queue_id=9
))



q = db.session.query(CranPackage.id)
update_registry.register(Update(
    job=CranPackage.set_num_downloads_score,
    query=q,
    queue_id=7
))

q = db.session.query(PypiPackage.id)
update_registry.register(Update(
    job=PypiPackage.set_num_downloads_score,
    query=q,
    queue_id=7
))

q = db.session.query(CranPackage.id)
update_registry.register(Update(
    job=CranPackage.set_pagerank_score,
    query=q,
    queue_id=7
))

q = db.session.query(PypiPackage.id)
update_registry.register(Update(
    job=PypiPackage.set_pagerank_score,
    query=q,
    queue_id=7
))


q = db.session.query(CranPackage.id)
update_registry.register(Update(
    job=CranPackage.set_num_citations_score,
    query=q,
    queue_id=7
))

q = db.session.query(PypiPackage.id)
update_registry.register(Update(
    job=PypiPackage.set_num_citations_score,
    query=q,
    queue_id=7
))

q = db.session.query(CranPackage.id)
update_registry.register(Update(
    job=CranPackage.set_host_reverse_deps,
    query=q,
    queue_id=8
))


q = db.session.query(CranPackage.id)
update_registry.register(Update(
    job=CranPackage.save_host_contributors,
    query=q,
    queue_id=8
))

q = db.session.query(PypiPackage.id)
update_registry.register(Update(
    job=PypiPackage.save_host_contributors,
    query=q,
    queue_id=8
))

q = db.session.query(Package.id)
update_registry.register(Update(
    job=Package.save_host_contributors,
    query=q,
    queue_id=8
))

q = db.session.query(Package.id)
# q = q.filter(Package.credit == None)
update_registry.register(Update(
    job=Package.save_all_people,
    query=q,
    queue_id=8
))

q = db.session.query(PypiPackage.id)
update_registry.register(Update(
    job=PypiPackage.set_igraph_data,
    query=q,
    queue_id=8,
    shortcut_fn=shortcut_igraph_data_dict
))

q = db.session.query(CranPackage.id)
update_registry.register(Update(
    job=CranPackage.set_igraph_data,
    query=q,
    queue_id=8,
    shortcut_fn=shortcut_igraph_data_dict
))









q = db.session.query(Person.id)
q = q.filter(Person.parsed_name == None)
update_registry.register(Update(
    job=Person.set_parsed_name,
    query=q,
    queue_id=8
))

q = db.session.query(Person.id)
q = q.filter(Person.github_about == text("'null'"))  # jsonb null, not sql NULL
update_registry.register(Update(
    job=Person.set_github_about,
    query=q,
    queue_id=8
))


q = db.session.query(CranPackage.id)
q = q.filter(CranPackage.tags == None)
update_registry.register(Update(
    job=CranPackage.set_tags,
    query=q,
    queue_id=8
))

q = db.session.query(Package.id)
q = q.filter(Package.github_owner != None)
q = q.filter(Package.github_contributors == None)
update_registry.register(Update(
    job=Package.set_github_contributors,
    query=q,
    queue_id=8
))


q = db.session.query(GithubRepoDeplines.id)
q = q.filter(GithubRepoDeplines.dependency_lines != None)
q = q.filter(GithubRepoDeplines.language == 'python')
q = q.filter(GithubRepoDeplines.pypi_dependencies == None)
update_registry.register(Update(
    job=GithubRepoDeplines.set_pypi_dependencies,
    query=q,
    queue_id=8,
    shortcut_fn=shortcut_get_pypi_package_names
))


q = db.session.query(Package.id)
q = q.filter(Package.github_contributors != None)
q = q.filter(Package.num_commits == None)
update_registry.register(Update(
    job=Package.set_num_committers_and_commits,
    query=q,
    queue_id=8
))

q = db.session.query(GithubRepo.id)
q = q.filter(GithubRepo.named_deps == None)
q = q.filter(GithubRepo.language == 'python')
update_registry.register(Update(
    job=GithubRepo.set_named_deps,
    query=q,
    queue_id=9
))


q = db.session.query(PypiPackage.id)
# q = q.filter(PypiPackage.pagerank_percentile == None)
update_registry.register(Update(
    job=PypiPackage.set_subscore_percentiles,
    query=q,
    queue_id=9,
    shortcut_fn=PypiPackage.shortcut_percentile_refsets
))

q = db.session.query(CranPackage.id)
# q = q.filter(CranPackage.pagerank_percentile == None)
update_registry.register(Update(
    job=CranPackage.set_subscore_percentiles,
    query=q,
    queue_id=9,
    shortcut_fn=CranPackage.shortcut_percentile_refsets
))

q = db.session.query(PypiPackage.id)
# q = q.filter(PypiPackage.pagerank_percentile == None)
update_registry.register(Update(
    job=PypiPackage.set_impact_percentiles,
    query=q,
    queue_id=9,
    shortcut_fn=PypiPackage.shortcut_percentile_refsets
))

q = db.session.query(CranPackage.id)
# q = q.filter(CranPackage.pagerank_percentile == None)
update_registry.register(Update(
    job=CranPackage.set_impact_percentiles,
    query=q,
    queue_id=9,
    shortcut_fn=CranPackage.shortcut_percentile_refsets
))




q = db.session.query(PypiPackage.id)
# q = q.filter(PypiPackage.impact == None)
update_registry.register(Update(
    job=PypiPackage.set_impact,
    query=q,
    queue_id=9
))

q = db.session.query(CranPackage.id)
# q = q.filter(CranPackage.impact == None)
update_registry.register(Update(
    job=CranPackage.set_impact,
    query=q,
    queue_id=9
))



q = db.session.query(Package.id)
q = q.filter(Package.github_owner != None)
q = q.filter(Package.github_api_raw == None)
update_registry.register(Update(
    job=Package.refresh_github_ids,
    query=q,
    queue_id=7
))


q = db.session.query(Package.id)
# q = q.filter(Package.credit == None)
update_registry.register(Update(
    job=Package.set_credit,
    query=q,
    queue_id=7
))


q = db.session.query(PypiPackage.id)
# q = q.filter(Package.num_citations_by_source == None)
update_registry.register(Update(
    job=PypiPackage.set_num_citations_by_source,
    query=q,
    queue_id=8
))

q = db.session.query(CranPackage.id)
# q = q.filter(Package.num_citations_by_source == None)
update_registry.register(Update(
    job=CranPackage.set_num_citations_by_source,
    query=q,
    queue_id=7
))


q = db.session.query(PypiPackage.id)
# q = q.filter(Package.num_citations_by_source == None)
update_registry.register(Update(
    job=PypiPackage.set_num_citations,
    query=q,
    queue_id=8
))

q = db.session.query(CranPackage.id)
# q = q.filter(Package.num_citations_by_source == None)
update_registry.register(Update(
    job=CranPackage.set_num_citations,
    query=q,
    queue_id=7
))


q = db.session.query(Package.id)
update_registry.register(Update(
    job=Package.dedup_people,
    query=q,
    queue_id=7
))

q = db.session.query(Package.id)
update_registry.register(Update(
    job=Package.dedup_special_cases,
    query=q,
    queue_id=7
))


q = db.session.query(PypiPackage.id)
q = q.filter(PypiPackage.ads_distinctiveness == None)
update_registry.register(Update(
    job=PypiPackage.set_ads_distinctiveness,
    query=q,
    queue_id=8
))

q = db.session.query(CranPackage.id)
q = q.filter(CranPackage.ads_distinctiveness == None)
update_registry.register(Update(
    job=CranPackage.set_ads_distinctiveness,
    query=q,
    queue_id=7
))

q = db.session.query(Person.id)
q = q.filter(Person.main_language == None)
update_registry.register(Update(
    job=Person.set_main_language,
    query=q,
    queue_id=7
))






q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_scores,
    query=q,
    queue_id=7
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_subscore_percentiles,
    query=q,
    queue_id=3,
    shortcut_fn=Person.shortcut_percentile_refsets    
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_impact,
    query=q,
    queue_id=3
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_impact_percentiles,
    query=q,
    queue_id=3,
    shortcut_fn=Person.shortcut_percentile_refsets    
))

