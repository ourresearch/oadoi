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
    shortcut_fn=person.shortcut_all_percentile_refsets
))


q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_first_name,
    query=q
))
q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.calculate,
    query=q
))


q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_attributes_and_works_from_orcid,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_impressions,
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
    job=Product.calculate_metrics,
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
    job=Person.set_tweeter_details,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_coauthors,
    query=q
))



q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_subscore_percentiles,
    query=q,
    shortcut_fn=person.shortcut_score_percentile_refsets
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_subscores,
    query=q
))

q = db.session.query(Product.id)
q = q.filter(Product.altmetric_score != None)
q = q.filter(Product.altmetric_score > 0)
update_registry.register(Update(
    job=Product.set_data_from_crossref,
    query=q
))

q = db.session.query(Product.id)
update_registry.register(Update(
    job=Product.set_in_doaj,
    query=q
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.set_subscores,
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
    shortcut_fn=lambda: ["oa_advocate"]
))

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.refresh_from_db,
    query=q,
    shortcut_fn=person.shortcut_all_percentile_refsets
))