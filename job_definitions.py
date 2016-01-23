from sqlalchemy import text
from sqlalchemy import orm

from app import db
from jobs import update_registry
from jobs import Update

from models.temp_orcid_profile import TempOrcidProfile
from models.product import Product
from models.profile import Profile




q = db.session.query(TempOrcidProfile.id)
q = q.filter(TempOrcidProfile.update_marker == None)
# q = q.filter(TempOrcidProfile.id.in_(['0000-0001-6187-6610', '0000-0003-1613-5981', '0000-0001-6728-7745']))
update_registry.register(Update(
    job=TempOrcidProfile.set_stuff,
    query=q
))



q = db.session.query(Product.id)
q = q.filter(Product.altmetric_api_raw == None)
q = q.order_by(Product.orcid)
update_registry.register(Update(
    job=Product.set_altmetric,
    query=q
))


q = db.session.query(Profile.id)
q = q.filter(Profile.t_index == None)
q = q.order_by(Profile.id)
update_registry.register(Update(
    job=Profile.set_t_index,
    query=q
))


q = db.session.query(Profile.id)
q = q.filter(Profile.num_products == None)
q = q.order_by(Profile.id)
update_registry.register(Update(
    job=Profile.set_num_products,
    query=q
))




