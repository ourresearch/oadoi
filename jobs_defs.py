from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from jobs import update_registry
from jobs import Update

from models.product import Product
from models.person import Person

q = db.session.query(Person.id)
q = q.filter(Person.orcid_id != None)
update_registry.register(Update(
    job=Person.refresh,
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

q = db.session.query(Person.id)
update_registry.register(Update(
    job=Person.assign_badges,
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



