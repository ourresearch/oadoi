from sqlalchemy import text
from sqlalchemy import orm

from app import db
from jobs import update_registry
from jobs import Update

from models.temp_orcid_profile import TempOrcidProfile
from models.product import Product




q = db.session.query(TempOrcidProfile.id)
q = q.filter(TempOrcidProfile.update_marker == None)
# q = q.filter(TempOrcidProfile.id.in_(['0000-0001-6187-6610', '0000-0003-1613-5981', '0000-0001-6728-7745']))
update_registry.register(Update(
    job=TempOrcidProfile.set_stuff,
    query=q
))



q = db.session.query(Product.id)
q = q.filter(Product.altmetric_api_raw == None)
# q = q.filter(TempOrcidProfile.id.in_(['0000-0001-6187-6610', '0000-0003-1613-5981', '0000-0001-6728-7745']))
update_registry.register(Update(
    job=Product.set_altmetric,
    query=q
))




