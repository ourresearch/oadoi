from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import JSONB

from app import db
import app
from jobs import update_registry
from jobs import Update

from publication import Publication

q = db.session.query(Publication.id)
update_registry.register(Update(
    job=Publication.refresh,
    query=q
))

