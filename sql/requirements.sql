-- counts unique libs listed in the requirements column. takes a while.
select jsonb_array_elements(requirements) as reqs, count(jsonb_array_elements(requirements)) as count 
	from github_repo where requirements is not NULL 
	group by reqs
	order by count desc
	limit 500;

-- is biopython there?
select * from github_repo where requirements::jsonb ? 'biopython';

-- repos we've checked
select count(*) from github_repo where reqs_file_tried;

-- we checked and found a setup.py or requirements.txt
select count(*) from github_repo where reqs_file is not NULL;

-- number of repos that has at least one requirement
select count(*) from github_repo where jsonb_array_length(requirements) > 0
