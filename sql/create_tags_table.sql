drop table tags;

create table tags as
select jsonb_array_elements_text(tags)::text as unique_tag, 
	count(jsonb_array_elements_text(tags)::text) as count,
	host as namespace
 	from package 
 	group by unique_tag, host
 	order by count desc;
 	
alter table tags add column id text;
update tags set id=(namespace||':'||unique_tag);



CREATE INDEX tags_unique_tag_idx 
	ON tags (unique_tag);

select * from tags order by count desc;


-- from http://stackoverflow.com/a/22106818  

create table package_tags as (
    select
        id as package_id,
        host as namespace,
        is_academic,
        jsonb_array_elements_text(tags) as tag,
        jsonb_array_length(tags) as num_tags_in_package
    from package) 


alter table tags add column count_academic int4;
update tags set count_academic=0 where count_academic is null
update tags set count_academic=s.c from (
		select tag, namespace, count(*) as c
		from package_tags 
		where package_tags.is_academic=true
		group by package_tags.namespace, package_tags.tag) as s
	where tags.namespace=s.namespace and tags.unique_tag=s.tag 


create table cooccurring_tags_one_way as (
    select 
        a.tag as tag1, 
        b.tag as tag2, 
        count(*) as c
    from package_tags a, package_tags b 
    where a.tag < b.tag 
    and a.package_id = b.package_id
    group by a.tag, b.tag
)

create view cooccurring_tags as (
    select 
        tag1, 
        tag2, 
        c 
        from cooccurring_tags_one_way
    union
    select 
        tag2 as tag1, 
        tag1 as tag2, 
        c 
        from cooccurring_tags_one_way
)
