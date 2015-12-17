create table dep_nodes_pypi as
(
select 'github' as source_namespace, id as source, jsonb_array_elements_text(named_deps) as depends_on
    from github_repo 
    where named_deps is not NULL 
    and language='python'
    and api_raw->>'fork' = 'false'
    and id not in
        (select github_owner||':'||github_repo_name from package where host='pypi' and github_owner is not null)
union    
select 'pypi' as source_namespace, project_name as source, jsonb_array_elements_text(host_reverse_deps) as depends_on
    from package where host_reverse_deps is not NULL 
    and host='pypi' 
) 