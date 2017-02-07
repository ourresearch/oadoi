from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import JSONB

from app import db
import app
from jobs import update_registry
from jobs import Update

from publication import Publication
from publication import Cached

q = db.session.query(Publication.id)
update_registry.register(Update(
    job=Publication.refresh,
    query=q,
    queue_id=0
))

q = db.session.query(Cached.id)
q = q.filter(Cached.content == None)
update_registry.register(Update(
    job=Cached.refresh,
    query=q,
    queue_id=0
))
