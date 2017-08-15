-- need to replace version with null for researcher version

select doi, url, is_best, license, updated, null::text as version, evidence, host_type, is_doaj_journal
from export_urls