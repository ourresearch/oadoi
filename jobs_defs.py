from sqlalchemy import text
from sqlalchemy import orm
from sqlalchemy import sql
from sqlalchemy import types
from sqlalchemy.dialects.postgresql import JSONB

import app
from app import db
from jobs import update_registry
from jobs import Update
from jobs import UpdateDbQueue

from publication import Pub
from date_range import DateRange

# q = db.session.query(Crossref.id)
# q = q.filter(Crossref.updated < '2017-03-24')
# q = q.filter(Crossref.response != None)
# q = q.filter(Crossref.response["color"].cast(types.Text) != None)
# text_query = u"""select doi from export_view_min where oa_color in ('green', 'gold') and open_urls is null"""

# text_query = u"""select id from crossref
#                 where crossref.response::jsonb ->> 'oa_color' is not null
#                   and not crossref.response::jsonb ? '_open_urls'"""

text_query = u"""select id from open_responses_20170327 open_resp where response_jsonb->>'_open_urls' is null and response_jsonb->>'evidence' = 'hybrid journal (via crossref license url)'"""



# text_query = u"""select id from dois_random_recent, crossref where dois_random_recent.doi=crossref.id and response is null"""
# text_query = u"""select lower(doi) from dois_oab order by doi desc"""
# update_registry.register(Update(
#     job=Crossref.run_subset,
#     query=text_query,
#     queue_id=1
# ))

# text_query = u"""select jsonb_array_elements_text(response_jsonb->'_closed_base_ids') from temp_oab where their_url is not null and response_jsonb->>'free_fulltext_url' is null"""
# # text_query = u"""select jsonb_array_elements_text(response_jsonb->'_closed_base_ids') from temp_oab"""
# # text_query = u"""select jsonb_array_elements_text(response_jsonb->'_closed_base_ids') from temp_oab union select jsonb_array_elements_text(response_jsonb->'_open_base_ids') from temp_oab"""
# update_registry.register(Update(
#     job=Base.find_fulltext,
#     query=text_query,
#     queue_id=1
# ))



# update_registry.register(UpdateDbQueue(
#     job=Base.find_fulltext,
#     action_table="base",
#     where="(body->'_source'->>'oa'='2' and not body->'_source' ? 'fulltext_url_dicts')",
#     queue_name="set_fulltext"
# ))


# update_registry.register(UpdateDbQueue(
#     job=Crossref.run_with_hybrid,
#     action_table="crossref",
#     where="(exists (select 1 from dois_wos dw where id=dw.doi))",
#     queue_name="run_with_hybrid"
# ))


# update_registry.register(UpdateDbQueue(
#     job=Crossref.run_with_skip_all_hybrid,
#     action_table="crossref",
#     # where="(id in (select jsonb_array_elements_text(response::jsonb->'_open_base_ids') from crossref where (response::jsonb->>'oa_color'='green')))",
#     where="(exists (select 1 from dois_hybrid_via_crossref d where crossref.id=d.doi))",
#     queue_name="skip_all_hybrid"
# ))


# create table green_base_ids as (select jsonb_array_elements_text(response::jsonb->'_open_base_ids') from crossref where (response::jsonb->>'oa_color'='green'))
# update_registry.register(UpdateDbQueue(
#     job=Base.find_fulltext,
#     action_table="base",
#     # where="(id in (select jsonb_array_elements_text(response::jsonb->'_open_base_ids') from crossref where (response::jsonb->>'oa_color'='green')))",
#     where="(exists (select 1 from base_green_ids_20170515 b where base.id=b.id)) ORDER BY ((((body -> '_source'::text) ->> 'random'::text)::numeric))",
#     # where="base.id in (select jsonb_array_elements_text(response_jsonb->'_closed_base_ids') from crossref where crossref.id in (select id from doi_queue))",
#     # where="queue='queue_me'",
#     # where="(position('ftunivpretoria', base.id) > 0)",
#     queue_name="base_green_ids_20170608"
# ))

update_registry.register(UpdateDbQueue(
    job=Pub.run,
    action_table="pub",
    where="(TRUE)",
    queue_name="run_201705011b"
))

update_registry.register(UpdateDbQueue(
    job=Pub.recalculate,
    action_table="pub"
))

update_registry.register(UpdateDbQueue(
    job=Pub.refresh,
    action_table="pub"
))

update_registry.register(UpdateDbQueue(
    job=Pub.run_with_hybrid,
    action_table="pub"
))

update_registry.register(UpdateDbQueue(
    job=DateRange.get_crossref_api_raw,
    action_table="date_range"
))

# run with python doi_queue.py --dates --run
update_registry.register(UpdateDbQueue(
    job=DateRange.get_unpaywall_events,
    action_table="date_range"
))

# run with python doi_queue.py --dates --run
update_registry.register(UpdateDbQueue(
    job=DateRange.get_pmh_events,
    action_table="date_range"
))