create or replace view export_main as (
 SELECT crossref.id AS doi,
    (crossref.response_jsonb_20171029 ->> 'is_oa')::bool AS is_oa,
    (crossref.response_jsonb_20171029 ->> 'data_standard')::numeric AS data_standard,
    crossref.response_jsonb_20171029 -> 'best_oa_location' ->> 'url'::text AS best_oa_location_url,
    crossref.response_jsonb_20171029 -> 'best_oa_location'->> 'host_type'::text AS best_oa_location_host_type,
    crossref.response_jsonb_20171029 -> 'best_oa_location'->> 'version'::text AS best_oa_location_version,
    crossref.response_jsonb_20171029 -> 'best_oa_location'->> 'license'::text AS best_oa_location_license,
    crossref.response_jsonb_20171029 -> 'best_oa_location'->> 'evidence'::text AS best_oa_location_evidence,
    crossref.response_jsonb_20171029 ->> 'title'::text AS title,
    crossref.response_jsonb_20171029 ->> 'issns_jsonb'::text AS journal_issns,
    crossref.response_jsonb_20171029 ->> 'journal_name'::text AS journal_name,
    (crossref.response_jsonb_20171029 ->> 'oa_journal_is_oa')::bool AS journal_is_oa,
    (crossref.response_jsonb_20171029 ->> 'oa_is_doaj_journal')::bool AS journal_is_in_doaj,
    crossref.response_jsonb_20171029 ->> 'publisher'::text AS publisher,
    crossref.updated
   FROM crossref
   )