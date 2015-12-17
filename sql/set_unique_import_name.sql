update package set unique_import_name=false where
import_name in
	(select import_name from
		(select import_name, count(id) as c
		from package 
		where host='pypi'
		group by import_name) with_count
		where c > 1
	) 