from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy import sql
from sqlalchemy import types
from sqlalchemy.dialects.postgresql import JSONB

import app
from app import db
from jobs import update_registry
from jobs import Update

from publication import Crossref
from publication import Base

# q = db.session.query(Crossref.id)
# q = q.filter(Crossref.updated < '2017-03-24')
# q = q.filter(Crossref.response != None)
# q = q.filter(Crossref.response["color"].cast(types.Text) != None)
# text_query = u"""select doi from export_view_min where oa_color in ('green', 'gold') and open_urls is null"""

# text_query = u"""select id from crossref
#                 where crossref.response::jsonb ->> 'oa_color' is not null
#                   and not crossref.response::jsonb ? '_open_urls'"""

text_query = u"""select id from open_responses_20170327 open_resp where response_jsonb->>'_open_urls' is null and response_jsonb->>'evidence' = 'hybrid journal (via crossref license url)'"""

update_registry.register(Update(
    job=Crossref.run_if_open,
    # query=q,
    query=text_query,
    queue_id=0
))


# text_query = u"""select id from dois_random_recent, crossref where dois_random_recent.doi=crossref.id and response is null"""
text_query = u"""select lower(doi) from dois_oab order by doi desc"""
update_registry.register(Update(
    job=Crossref.run_subset,
    query=text_query,
    queue_id=1
))

text_query = u"""select jsonb_array_elements_text(response_jsonb->'_closed_base_ids') from temp_oab union select jsonb_array_elements_text(response_jsonb->'_open_base_ids') from temp_oab"""
update_registry.register(Update(
    job=Base.find_fulltext,
    query=text_query,
    queue_id=1
))
