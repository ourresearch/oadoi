create or replace view export_main_for_researchers as (
SELECT crossref.id AS doi,
    crossref.updated,
    CASE
        WHEN (crossref.response_jsonb ->> 'scrape_updated'::text) = ''::text THEN 1
        ELSE 2
    END AS data_standard,
    response_jsonb ->> 'is_oa'::text AS is_oa,
    response_jsonb ->> 'journal_issns'::text AS journal_issns,
    response_jsonb ->> 'journal_name'::text AS journal_name,
    response_jsonb ->> 'oa_evidence'::text AS oa_evidence,
    response_jsonb ->> 'oa_host_type'::text AS oa_host_type,
    response_jsonb ->> 'oa_is_doaj_journal'::text AS oa_is_doaj_journal,
    response_jsonb ->> 'oa_license'::text AS oa_license,
    response_jsonb ->> 'oa_url'::text AS oa_url,
    null::text AS oa_version,
    response_jsonb ->> 'publisher'::text AS publisher,
    response_jsonb ->> 'title'::text AS title
   FROM crossref
)