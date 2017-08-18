create or replace view export_main_for_researchers as (
 SELECT crossref.id AS doi,
    (crossref.response_jsonb ->> 'is_oa')::bool AS is_oa,
    (crossref.response_jsonb ->> 'data_standard')::numeric AS data_standard,
    crossref.response_jsonb ->> 'oa_url'::text AS oa_url,
    crossref.response_jsonb ->> 'oa_host_type'::text AS oa_host_type,
    crossref.response_jsonb ->> 'oa_version'::text AS oa_version,
    crossref.response_jsonb ->> 'oa_license'::text AS oa_license,
    crossref.response_jsonb ->> 'oa_evidence'::text AS oa_evidence,
    crossref.response_jsonb ->> 'title'::text AS title,
    crossref.response_jsonb ->> 'journal_issns'::text AS journal_issns,
    crossref.response_jsonb ->> 'journal_name'::text AS journal_name,
    (crossref.response_jsonb ->> 'oa_is_doaj_journal')::bool AS journal_is_oa,
    crossref.response_jsonb ->> 'publisher'::text AS publisher,
    crossref.updated
   FROM crossref
   )