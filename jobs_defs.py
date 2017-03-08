from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy import sql
from sqlalchemy.dialects.postgresql import JSONB

import app
from app import db
from jobs import update_registry
from jobs import Update

from publication import Crossref

q = db.session.query(Crossref.id)
# q = q.filter(Crossref.response == None)
update_registry.register(Update(
    job=Crossref.run,
    query=q,
    queue_id=0
))


text_query = u"""select id from dois_random_recent, crossref where dois_random_recent.doi=crossref.id"""
rows = db.engine.execute(sql.text(text_query)).fetchall()
ids = [row[0] for row in rows]
update_registry.register(Update(
    job=Crossref.run_subset,
    query=ids,
    queue_id=1
))

