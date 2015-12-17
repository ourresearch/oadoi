-- counts unique libs listed in the pypi_dependencies column. takes a while.
select jsonb_array_elements(pypi_dependencies) as deps, count(jsonb_array_elements(pypi_dependencies)) as count 
	from github_repo where pypi_dependencies is not NULL 
	group by deps
	order by count desc
	limit 100;

