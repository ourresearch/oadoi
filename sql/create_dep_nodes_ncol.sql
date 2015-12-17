
create table dep_nodes_ncol_cran_reverse as
(
select 'github:'||id as used_by, jsonb_array_elements_text(named_deps) as package
    from github_repo 
    where named_deps is not NULL 
    and language = 'r'
    and login != 'cran'
    and api_raw->>'fork' = 'false'
    and id not in
        (select github_owner||':'||github_repo_name from package where host='cran' and github_owner is not null)
union    
select jsonb_array_elements_text(host_reverse_deps) as used_by , project_name as package
    from package where host_reverse_deps is not NULL 
    and host='cran' 
) 


create table dep_nodes_ncol_pypi_reverse as
    select * from 
        (
        select 'github:'||id as used_by, jsonb_array_elements_text(named_deps) as package
            from github_repo 
            where named_deps is not NULL 
            and language='python'
            and api_raw->>'fork' = 'false'
            and id not in
                (select github_owner||':'||github_repo_name from package where host='pypi' and github_owner is not null)
        union    
        select project_name as used_by, jsonb_array_elements_text(host_deps) as package
            from package where host_deps is not NULL 
            and host='pypi' 
        ) s
    where package in 
        (select project_name from package where host='pypi' and has_best_import_name=True)

CREATE INDEX dep_nodes_cran_package_idx 
    ON public.dep_nodes_ncol_cran_reverse (package);
CREATE INDEX dep_nodes_pypi_package_idx 
    ON public.dep_nodes_ncol_pypi_reverse (package);
CREATE INDEX dep_nodes_cran_used_by_idx 
    ON public.dep_nodes_ncol_cran_reverse (used_by);
CREATE INDEX dep_nodes_pypi_used_by_idx 
    ON public.dep_nodes_ncol_cran_reverse (used_by) ;   
    

select * from dep_nodes_ncol_pypi_reverse limit 1000


select distinct on (import_name) id, import_name, num_downloads 
from package 
where host='pypi'
and unique_import_name=False
order by import_name, num_downloads desc
limit 10