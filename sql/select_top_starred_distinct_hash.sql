(SELECT DISTINCT ON (setup_py_hash) login, repo_name, setup_py_hash, (api_raw->>'stargazers_count')::int as stars
    FROM github_repo
    where setup_py_hash is not null
    ORDER BY setup_py_hash, (api_raw->>'stargazers_count')::int DESC
)