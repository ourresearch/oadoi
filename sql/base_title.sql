-- run this by running this in local oadoi directory
-- heroku pg:psql < sql/base_title.sql

CREATE EXTENSION unaccent;

CREATE OR REPLACE FUNCTION f_unaccent(text)
  RETURNS text AS
	$func$
	-- need to have run CREATE EXTENSION unaccent
	-- from http://stackoverflow.com/a/11007216/596939
	SELECT public.unaccent('public.unaccent', $1)  -- schema-qualify function and dictionary
	$func$
	LANGUAGE sql IMMUTABLE;

CREATE or replace FUNCTION normalize_title_v2(title text) RETURNS text
    AS $$
    declare val text := '';
    begin
    	-- just first n characters
    	val := substring(title, 1, 500);

    	-- lowercase
    	val := lower(val);

    	-- unaccent
    	-- need to have run 'CREATE EXTENSION unaccent'
    	-- and created f_unaccent from http://stackoverflow.com/a/11007216/596939
    	val := f_unaccent(val);

    	-- remove articles and common prepositions
    	val := regexp_replace(val, '\y(the|a|an|of|to|in|for|on|by|with|at}from)\y', '', 'g');

    	-- remove html tags
    	-- the kind in titles are simple <i> etc, so this is simple
    	val := regexp_replace(val, '<[^>]+>', ' ', 'g');

    	-- remove everything except alphas
    	val := regexp_replace(val, '[^a-z]', '', 'g');
        return val;
    end;
    $$
    LANGUAGE plpgsql
    IMMUTABLE
    RETURNS NULL ON NULL INPUT;

select body->'_source'->>'title', normalize_title_v2(body->'_source'->>'title') from base
where random() < 0.1 limit 10;

-- drop index base_normalize_title_v2_idx;

CREATE INDEX base_normalize_title_v2_idx ON base (normalize_title_v2(body->'_source'->>'title'));


CREATE or replace FUNCTION get_title(body jsonb) RETURNS text
    AS $$
    declare val text := '';
    begin
    	return body->'_source'->>'title';
    end;
    $$
    LANGUAGE plpgsql
    IMMUTABLE
    RETURNS NULL ON NULL INPUT;

create or replace view crossref_title_view as
(select id, api->'_source'->>'title' as title, normalize_title_v2(api->'_source'->>'title') as normalized_title
from pub
where length(normalize_title_v2(api->'_source'->>'title')) >= 21);

create or replace view base_title_view as
(select id, doi, body->'_source'->>'base' as title, normalize_title_v2(body->'_source'->>'title') as normalized_title, body
from base);

create or replace view pmh_title_view as
(
 SELECT id,
    doi,
    title,
    normalize_title_v2(title) AS normalized_title
   FROM pmh_record
)
