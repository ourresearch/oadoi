
update person set is_organization=false;

update person set is_organization=true 
	where false	 -- just to comment out other things easily
	or name ilike '%organiz%'
	or name ilike '%foundat%'
	or name ilike '%technolo%'
	or name ilike '% labor%'
	or name ilike '% lab'
	or name ilike '% labs'
	or name ilike '%center%'
	or name ilike '%centre%'
	or name ilike '%consulting%'
	or name ilike '%corporation%'
	or name ilike '%institu%'
	or name ilike '%project%'
	or name ilike '%group%'
	or name ilike '%alliance%'
	or name ilike '%solutions%'
	or name ilike '%contributor%'
	or name ilike '%community%'
	or name ilike '%authors%'
	or name ilike 'inc %'
	or name ilike 'inc'
	or name ilike 'inc. %'
	or name ilike '% the %'
	or name ilike 'the %'
	or name ilike '%library%'
	or name ilike '%university%'
	or name ilike '%university%'
	or name ilike '% team%'
	or name ilike '%developers%'
	or name ilike '% inc.'
	or name ilike '% inc'
	or name ilike '% llc'
	or name ilike '% incorp%'
	or name ilike '% limited%'
	or name like '% AG'
	or name ilike '% GmbH'
	or github_about->>'type' = 'Organization'
	or name in ('Tryton', 'OpenERP SA', 'OpenStack', 'Logilab', 'IBM', 
		'The fellowship of the packaging', 'Check your git settings!', 
		'Twitter', 'GNU Solidario', 'hfpython')
