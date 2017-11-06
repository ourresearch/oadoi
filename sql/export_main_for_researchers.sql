create or replace view export_main_for_researchers as (
 SELECT pub.id AS doi,
    (pub.response_jsonb ->> 'is_oa')::bool AS is_oa,
    (pub.response_jsonb ->> 'data_standard')::numeric AS data_standard,
    pub.response_jsonb ->> 'oa_url'::text AS best_oa_location_url,
    pub.response_jsonb ->> 'oa_host_type'::text AS best_oa_location_host_type,
    pub.response_jsonb ->> 'oa_version'::text AS best_oa_location_version,
    pub.response_jsonb ->> 'oa_license'::text AS best_oa_location_license,
    pub.response_jsonb ->> 'oa_evidence'::text AS best_oa_location_evidence,
    pub.response_jsonb ->> 'title'::text AS title,
    (crossref_api.api_raw ->> 'ISSN')::text AS journal_issns,
    pub.response_jsonb ->> 'journal_name'::text AS journal_name,
    (pub.response_jsonb ->> 'oa_journal_is_oa')::bool AS journal_is_oa,
    (pub.response_jsonb ->> 'oa_is_doaj_journal')::bool AS journal_is_in_doaj,
    pub.response_jsonb ->> 'publisher'::text AS publisher,
    pub.updated
   FROM pub, crossref_api
   where pub.id = crossref_api.doi
   )