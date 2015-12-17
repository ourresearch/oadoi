
-- before checking for cran github IDs in github metadata
select count(*) from package where host='pypi' and github_repo_name is not null
-- 1,633 github / 7,069 total = 23% of cran repos on github
-- 40,177 github / 64119 total = 63% of pypi on github

select count(*) from package where github_contributors is not null and host='cran'
--882
-------------


