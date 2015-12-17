
-- make the project_names table
select *
into project_names
from (
	select 'Python' as language, api_raw::jsonb->'info'->>'name' as name, api_raw::jsonb->'info'->>'summary' as about from pypi_project 
	union 
	select 'R', api_raw::jsonb->>'Package', api_raw::jsonb->>'Title' from cran_project 
	order by name
) as foo;

