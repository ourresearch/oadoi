from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import JSONB

from app import db
import app
from jobs import update_registry
from jobs import Update

from models.product import Product
from models.person import Person
from models import person

q = db.session.query(Person.id)
q = q.filter(Person.orcid_id != None)
update_registry.register(Update(
    job=Person.refresh,
    query=q,
    shortcut_fn=person.shortcut_all_percentile_refsets,
    queue_id=0
))


q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_hybrid,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.calculate,
    query=q,
    shortcut_fn=person.shortcut_all_percentile_refsets
))


q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_from_orcid,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_mendeley,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_mendeley_sums,
    query=q
))

q = db.session.query(Product.id)
q = q.filter(Product.altmetric_api_raw != None)
q = q.filter(Product.altmetric_api_raw != {})
q = q.filter(Product.event_dates == None)
update_registry.register(Update(
    job=Product.set_event_dates,
    query=q
))

q = db.session.query(Product.id)
q = q.filter(Product.altmetric_api_raw != None)
q = q.filter(Product.altmetric_score == None)
update_registry.register(Update(
    job=Product.set_altmetric_score,
    query=q
))

q = db.session.query(Product.id)
q = q.filter(Product.altmetric_api_raw != None)
update_registry.register(Update(
    job=Product.calculate,
    query=q
))

q = db.session.query(Product.id)
q = q.filter(Product.altmetric_api_raw != None)
update_registry.register(Update(
    job=Product.set_altmetric_id,
    query=q
))

q = db.session.query(Product.id)
q = q.filter(Product.post_counts != None)
q = q.filter(Product.post_counts != {})
update_registry.register(Update(
    job=Product.set_post_details,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_post_details,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_coauthors,
    query=q
))


q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_is_open_temp,
    query=q,
    queue_id=1
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_is_open,
    query=q,
    queue_id=0
))

q = db.session.query(Product.id)
q = q.filter(Product.altmetric_score != None)
q = q.filter(Product.altmetric_score > 0)
update_registry.register(Update(
    job=Product.set_data_from_crossref,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_publisher,
    query=q
))




q = db.session.query(Person.id)
# q = q.filter(Person.campaign.in_(["2015_with_urls"]))
# q = q.filter(Person.campaign != "2015_with_urls")
# q = q.filter(Person.campaign.in_(["impactstory_nos", "impactstory_subscribers"]))  #@todo remove this
# q = q.filter(Person.orcid_id.in_([
#             "0000-0002-6133-2581",
#             "0000-0002-0159-2197",
#             "0000-0003-1613-5981",
#             "0000-0003-1419-2405",
#             "0000-0001-6187-6610",
#             "0000-0001-6728-7745"]))
update_registry.register(Update(
    job=Person.set_badge_percentiles,
    query=q,
    shortcut_fn=person.shortcut_badge_percentile_refsets
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.assign_badges,
    query=q,
    shortcut_fn=lambda: ["clean_sweep_using_mendeley", "interdisciplinarity", "librarian", "teaching", "big_in_japan_using_mendeley", "reading_level_using_mendeley", "global_reach_using_mendeley", "global_south_using_mendeley"]
))

q = db.session.query(Person.id)
# q = q.filter(Person.updated < '2016-04-10 10:00:51.972209')
update_registry.register(Update(
    job=Person.refresh_from_db,
    query=q,
    shortcut_fn=person.shortcut_all_percentile_refsets
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.all_products_set_biblio_from_orcid,
    query=q
))

