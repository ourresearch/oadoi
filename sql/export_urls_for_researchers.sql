-- need to replace version with null for researcher version
create or replace view all_locations as (
select  all_locations.*
from    pub c
cross join lateral
        jsonb_to_recordset(locations) as all_locations(doi text, url text, is_best bool, license text, updated timestamp, version text, evidence text, host_type text, is_doaj_journal bool)
        );

create or replace view export_urls_for_researchers AS
(
select doi, is_best, url, host_type, null as version, license, evidence, updated
from all_locations
)

create or replace view export_urls AS
(
select doi, is_best, url, host_type, version, license, evidence, updated
from all_locations
)