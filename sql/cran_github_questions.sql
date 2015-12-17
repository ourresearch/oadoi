-- how many cran projects have any url at all?
select api_raw::jsonb->>'URL' from cran_project where api_raw::jsonb ? 'URL'


-- how many have a github-lookin' url?
select github_owner, github_repo_name, api_raw::jsonb->>'URL' from cran_project where api_raw::jsonb->>'URL' like '%github%' limit 100;

-- how about github.io ones?
select api_raw::jsonb->>'URL' from cran_project where api_raw::jsonb->>'URL' like '%github.io%'