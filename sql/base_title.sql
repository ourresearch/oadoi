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

CREATE or replace FUNCTION normalize_title(title text) RETURNS text
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

    	-- remove articles
    	val := regexp_replace(val, '\y(the|a|an)\y', '', 'g');

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

select body->'_source'->>'title', normalize_title(body->'_source'->>'title') from base
where random() < 0.1 limit 10;

-- drop index base_normalize_title_idx;

CREATE INDEX base_normalize_title_idx ON base (normalize_title(body->'_source'->>'title'));

