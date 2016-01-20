from sqlalchemy import text
from sqlalchemy import orm

from app import db
from jobs import update_registry
from jobs import Update

from models.temp_orcid_profile import TempOrcidProfile




q = db.session.query(TempOrcidProfile.id)
q = q.filter(TempOrcidProfile.twitter == None)
update_registry.register(Update(
    job=TempOrcidProfile.set_twitter,
    query=q
))





