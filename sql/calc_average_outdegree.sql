create table outdegree as
(
	select d.used_by as dep_node_name, 'pypi' as host, count(*) as outdegree
	from dep_nodes_ncol_pypi_reverse d
	group by d.used_by
	order by outdegree asc
) 
union
(
	select d.used_by as dep_node_name, 'cran' as host, count(*) as outdegree
	from dep_nodes_ncol_cran_reverse d
	group by d.used_by
	order by outdegree asc
)

create table average_outdegree_of_used_by as
(
	select host||':'||d.package as id, sum(outdegree)/count(*) as average_outdegree
	from outdegree, dep_nodes_ncol_pypi_reverse d
	where outdegree.host='pypi'
	and outdegree.dep_node_name = d.used_by
	group by host, d.package
) 
union
(
	select host||':'||d.package as id, sum(outdegree)/count(*) as average_outdegree
	from outdegree, dep_nodes_ncol_cran_reverse d
	where outdegree.host='cran'
	and outdegree.dep_node_name = d.used_by
	group by host, d.package
)

update package set avg_outdegree_of_neighbors=average_outdegree 
from average_outdegree_of_used_by
where average_outdegree_of_used_by.id = package.id
