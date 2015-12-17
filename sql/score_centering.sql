select count(*) 
from package
where host = 'cran'
and num_downloads is not null

select count(*) 
from package
where host = 'pypi'
and num_downloads is not null

select * from (
select host, num_downloads, row_number() OVER (order by num_downloads desc) as rnum from package 
where host = 'cran'
) s where rnum=(7057*0.01)::int --99th

select * from (
select host, num_downloads, row_number() OVER (order by num_downloads desc) as rnum from package 
where host = 'pypi'
) s where rnum=(57244*0.01)::int --99th



select count(*) 
from package
where host = 'cran'
and pagerank is not null

select count(*) 
from package
where host = 'pypi'
and pagerank is not null


select * from (
select host, pagerank, row_number() OVER (order by pagerank desc) as rnum from package 
where host = 'cran'
and pagerank is not null
) s where rnum=(5863*0.01)::int --99th

select * from (
select host, pagerank, row_number() OVER (order by pagerank desc) as rnum from package 
where host = 'pypi'
and pagerank is not null
) s where rnum=(40120*0.01)::int --99th


select * from (
select id, host, pagerank, row_number() OVER (order by pagerank desc) as rnum from package 
where host = 'cran'
and pagerank is not null
) s where rnum=(5863*0.5)::int --50th

select * from (
select id, host, pagerank, row_number() OVER (order by pagerank desc) as rnum from package 
where host = 'pypi'
and pagerank is not null
) s where rnum=(40120*0.5)::int --50th