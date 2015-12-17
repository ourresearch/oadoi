create table top_named_deps as 
select jsonb_array_elements_text(named_deps) as project_name, count(jsonb_array_elements_text(named_deps))::int as named_dep_count 
    from github_repo where named_deps is not NULL 
    group by project_name