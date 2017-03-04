from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import JSONB

from app import db
import app
from jobs import update_registry
from jobs import Update

from publication import Cached
from publication import DoiResult


q = db.session.query(Cached.id)
q = q.filter(Cached.content == None)
update_registry.register(Update(
    job=Cached.refresh,
    query=q,
    queue_id=0
))

q = db.session.query(DoiResult.id)
q = q.filter(DoiResult.hello == None)
update_registry.register(Update(
    job=DoiResult.say_hello,
    query=q,
    queue_id=0
))

from sqlalchemy import sql
# q = u"""select doi from dois_random"""
q = u"""select doi from dois_random, doi_result where dois_random.doi=doi_result.id and content->>'oa_color'='green'"""
rows = db.engine.execute(sql.text(q)).fetchall()
dois = [row[0] for row in rows]
update_registry.register(Update(
    job=DoiResult.run_crossref,
    query=dois,
    queue_id=0
))