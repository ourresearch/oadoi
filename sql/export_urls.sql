create or replace view all_locations as (
select  all_locations.*
from    crossref c
cross join lateral
        jsonb_to_recordset(locations) as all_locations(doi text, url text, is_best bool, license text, updated timestamp, version text, evidence text, host_type text, is_doaj_journal bool)
        );


create or replace view export_urls as (
select  all_locations.*
from    crossref c
cross join lateral
        jsonb_to_recordset(locations) as all_locations(doi text, url text, is_best bool, license text, updated timestamp, version text, evidence text, host_type text, is_doaj_journal bool)
        );

