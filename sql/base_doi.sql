CREATE or replace FUNCTION doi_from_urls(body jsonb) RETURNS text
    AS $$
    declare urls jsonb;
    declare url text;
    declare doi text := null;

    begin
    	urls := body#>>'{_source, urls}';
    	doi := null;

	    FOR url in select * from jsonb_array_elements(urls)
	    LOOP
	    	-- case insensitive contains
	    	if url ~* 'doi.org/' then
		    	doi := substring(url from 'doi.org/(.*)\"');
		    	doi := lower(doi);
		    end if;
	    END LOOP;
        return doi;
    end;
    $$
    LANGUAGE plpgsql
    IMMUTABLE
    RETURNS NULL ON NULL INPUT;

