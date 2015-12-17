-- all the names and descriptions of repos
select 'Python' as language, api_raw::jsonb->'info'->>'name' as name, api_raw::jsonb->'info'->>'summary' as about from pypi_project 
union 
select 'R', api_raw::jsonb->>'Package', api_raw::jsonb->>'Title' from cran_project 
order by name
limit 1000;