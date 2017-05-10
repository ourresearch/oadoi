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
#     queue_table="base",
#     where="(body->'_source'->>'oa'='2' and not body->'_source' ? 'fulltext_url_dicts')",
#     queue_name="set_fulltext"
# ))

update_registry.register(UpdateDbQueue(
    job=Crossref.run,
    queue_table="crossref",
    where="(id is not null)",
    queue_name="run_20170305"
))


# update_registry.register(UpdateDbQueue(
#     job=Crossref.run_with_realtime_scraping,
#     queue_table="crossref",
#     where="(exists (select 1 from dois_wos dw where id=dw.doi))",
#     queue_name="run_with_realtime_scraping"
# ))


# create table green_base_ids as (select jsonb_array_elements_text(response::jsonb->'_open_base_ids') from crossref where (response::jsonb->>'oa_color'='green'))
update_registry.register(UpdateDbQueue(
    job=Base.find_fulltext,
    queue_table="base",
    # where="(id in (select jsonb_array_elements_text(response::jsonb->'_open_base_ids') from crossref where (response::jsonb->>'oa_color'='green')))",
    where="(exists (select 1 from green_base_ids gbi where crossref.id=gbi.id))",
    queue_name="green_base_rescrape"
))

# update_registry.register(UpdateDbQueue(
#     job=Crossref.run_with_skip_all_hybrid,
#     queue_table="crossref",
#     # where="(id in (select jsonb_array_elements_text(response::jsonb->'_open_base_ids') from crossref where (response::jsonb->>'oa_color'='green')))",
#     where="(exists (select 1 from dois_hybrid_via_crossref d where crossref.id=d.doi))",
#     queue_name="skip_all_hybrid"
# ))

update_registry.register(UpdateDbQueue(
    job=Crossref.run_with_skip_all_hybrid,
    queue_table="crossref",
    where="(exists (select 1 from dois_random_articles_1mil dra where crossref.id=dra.doi))",
    queue_name="skip_all_hybrid_20170429"
))

update_registry.register(UpdateDbQueue(
    job=Crossref.run_with_realtime_scraping,
    queue_table="crossref",
    where="(exists (select 1 from dois_wos_stefi dra where crossref.id=dra.doi))",
    queue_name="run_with_all_hybrid_20170510a"
))

