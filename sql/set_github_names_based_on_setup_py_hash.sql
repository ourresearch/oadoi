update package set github_owner=login, github_repo_name=repo_name, bucket='{"matched_from_setup_py":true}'::jsonb
from 
(SELECT DISTINCT ON (setup_py_hash) login, repo_name, setup_py_hash, (api_raw->>'stargazers_count')::int as stars
    FROM github_repo
    where setup_py_hash is not null
    ORDER BY setup_py_hash, (api_raw->>'stargazers_count')::int DESC
) as distinct_github_hash
where 
package.github_repo_name is null 
and package.host = 'pypi'
and package.setup_py_hash = distinct_github_hash.setup_py_hash