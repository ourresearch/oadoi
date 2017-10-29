create or replace view export_main as (
 SELECT crossref.id AS doi,
    (crossref.response_jsonb ->> 'is_oa')::bool AS is_oa,
    (crossref.response_jsonb ->> 'data_standard')::numeric AS data_standard,
    crossref.response_jsonb ->> 'oa_url'::text AS best_oa_location_url,
    crossref.response_jsonb ->> 'oa_host_type'::text AS best_oa_location_host_type,
    crossref.response_jsonb ->> 'oa_version'::text AS best_oa_location_version,
    crossref.response_jsonb ->> 'oa_license'::text AS best_oa_location_license,
    crossref.response_jsonb ->> 'oa_evidence'::text AS best_oa_location_evidence,
    crossref.response_jsonb ->> 'title'::text AS title,
    (crossref_api.api_raw ->> 'ISSN')::text AS journal_issns,
    crossref.response_jsonb ->> 'journal_name'::text AS journal_name,
    (crossref.response_jsonb ->> 'oa_journal_is_oa')::bool AS journal_is_oa,
    (crossref.response_jsonb ->> 'oa_is_doaj_journal')::bool AS journal_is_in_doaj,
    crossref.response_jsonb ->> 'publisher'::text AS publisher,
    crossref.updated
   FROM crossref, crossref_api
   where crossref.id = crossref_api.doi
   )