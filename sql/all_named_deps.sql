create view all_named_deps as
select login, repo_name, jsonb_array_elements_text(named_deps) as project_name 
    from github_repo where named_deps is not NULL 