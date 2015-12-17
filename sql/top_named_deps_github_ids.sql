create view top_named_deps_github_ids as 
select top_named_deps.project_name, named_dep_count, github_owner, github_repo_name from top_named_deps
left outer join package
on top_named_deps.project_name=package.project_name
order by named_dep_count desc