-- need to replace version with null for researcher version

create or replace view export_urls_for_researchers AS
(
select doi, url, is_best, license, now() as updated, null::text as version, evidence, host_type, is_doaj_journal
from export_urls
)