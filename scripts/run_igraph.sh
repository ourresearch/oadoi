# run this with 
# heroku run --size=performance-l sh scripts/run_igraph.sh

echo "exporting CRAN dep nodes from db"
psql $DATABASE_URL --command="\copy dep_nodes_ncol_cran_reverse to 'dep_nodes_ncol.txt' DELIMITER ' ';"
echo "running CRAN igraph data through igraph and storing stats in db"
python update.py CranPackage.set_igraph_data --limit=100000 --chunk=100 --no-rq

echo "exporting PYPI dep nodes from db"
psql $DATABASE_URL --command="\copy dep_nodes_ncol_pypi_reverse to 'dep_nodes_ncol.txt' DELIMITER ' ';"
echo "running PYPI igraph data through igraph and storing stats in db"
python update.py PypiPackage.set_igraph_data --limit=100000 --chunk=100 --no-rq

echo "done!  :)"