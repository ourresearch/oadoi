
drop view export_main_changed_with_versions;
create or replace view export_main_changed_with_versions as (
 SELECT pub.id AS doi,
    (pub.response_jsonb ->> 'is_oa')::bool AS is_oa,
    (pub.response_jsonb ->> 'data_standard')::numeric AS data_standard,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url'::text AS best_oa_location_url,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url_for_landing_page'::text AS best_oa_location_url_for_landing_page,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url_for_pdf'::text AS best_oa_location_url_for_pdf,
    pub.response_jsonb -> 'best_oa_location'->> 'host_type'::text AS best_oa_location_host_type,
    pub.response_jsonb -> 'best_oa_location'->> 'version'::text AS best_oa_location_version,
    pub.response_jsonb -> 'best_oa_location'->> 'license'::text AS best_oa_location_license,
    pub.response_jsonb -> 'best_oa_location'->> 'evidence'::text AS best_oa_location_evidence,
    pub.response_jsonb ->> 'title'::text AS title,
    pub.response_jsonb ->> 'journal_issns'::text AS journal_issns,
    pub.response_jsonb ->> 'journal_name'::text AS journal_name,
    (pub.response_jsonb ->> 'journal_is_oa')::bool AS journal_is_oa,
    pub.response_jsonb ->> 'publisher'::text AS publisher,
    pub.response_jsonb -> 'year' AS year,
    pub.response_jsonb ->> 'genre'::text AS genre,
    pub.updated AS updated
FROM pub
  WHERE pub.last_changed_date IS NOT NULL
)

drop view export_main_with_versions;
create or replace view export_main_with_versions as (
 SELECT pub.id AS doi,
    (pub.response_jsonb ->> 'is_oa')::bool AS is_oa,
    (pub.response_jsonb ->> 'data_standard')::numeric AS data_standard,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url'::text AS best_oa_location_url,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url_for_landing_page'::text AS best_oa_location_url_for_landing_page,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url_for_pdf'::text AS best_oa_location_url_for_pdf,
    pub.response_jsonb -> 'best_oa_location'->> 'host_type'::text AS best_oa_location_host_type,
    pub.response_jsonb -> 'best_oa_location'->> 'version'::text AS best_oa_location_version,
    pub.response_jsonb -> 'best_oa_location'->> 'license'::text AS best_oa_location_license,
    pub.response_jsonb -> 'best_oa_location'->> 'evidence'::text AS best_oa_location_evidence,
    pub.response_jsonb ->> 'title'::text AS title,
    pub.response_jsonb ->> 'journal_issns'::text AS journal_issns,
    pub.response_jsonb ->> 'journal_name'::text AS journal_name,
    (pub.response_jsonb ->> 'journal_is_oa')::bool AS journal_is_oa,
    pub.response_jsonb ->> 'publisher'::text AS publisher,
    pub.response_jsonb -> 'year' AS year,
    pub.response_jsonb ->> 'genre'::text AS genre,
    pub.updated AS updated
FROM pub
   )

drop view export_main_no_versions;
create or replace view export_main_no_versions as (
  SELECT pub.id AS doi,
    (pub.response_jsonb ->> 'is_oa'::text)::boolean AS is_oa,
    (pub.response_jsonb ->> 'data_standard'::text)::numeric AS data_standard,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url'::text AS best_oa_location_url,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url_for_landing_page'::text AS best_oa_location_url_for_landing_page,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'url_for_pdf'::text AS best_oa_location_url_for_pdf,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'host_type'::text AS best_oa_location_host_type,
    NULL::text AS best_oa_location_version,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'license'::text AS best_oa_location_license,
    (pub.response_jsonb -> 'best_oa_location'::text) ->> 'evidence'::text AS best_oa_location_evidence,
    pub.response_jsonb ->> 'title'::text AS title,
    pub.response_jsonb ->> 'journal_issns'::text AS journal_issns,
    pub.response_jsonb ->> 'journal_name'::text AS journal_name,
    (pub.response_jsonb ->> 'journal_is_oa'::text)::boolean AS journal_is_oa,
    pub.response_jsonb ->> 'publisher'::text AS publisher,
    pub.response_jsonb -> 'year'::text AS year,
    pub.response_jsonb ->> 'genre'::text AS genre,
    pub.updated AS updated
   FROM pub
   )
