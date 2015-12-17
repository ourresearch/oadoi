select * from (
	select id, tags, summary, jsonb_array_elements(tags)::text as my_tag from package 
) s
where my_tag like '%genetics%'
limit 1000
