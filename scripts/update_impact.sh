heroku run --size=performance-l python update.py CranPackage.set_num_downloads_score --no-rq --limit=100000 
heroku run --size=performance-l python update.py PypiPackage.set_num_downloads_score --no-rq --limit=100000 

heroku run --size=performance-l python update.py CranPackage.set_pagerank_score --no-rq --limit=100000 
heroku run --size=performance-l python update.py PypiPackage.set_pagerank_score --no-rq --limit=100000 

heroku run --size=performance-l python update.py CranPackage.set_subscore_percentiles --no-rq --limit=100000 
heroku run --size=performance-l python update.py PypiPackage.set_subscore_percentiles --no-rq --limit=100000 

heroku run --size=performance-l python update.py CranPackage.set_impact --no-rq --limit=100000
heroku run --size=performance-l python update.py PypiPackage.set_impact --no-rq --limit=100000

heroku run --size=performance-l python update.py CranPackage.set_impact_percentiles --no-rq --limit=100000 
heroku run --size=performance-l python update.py PypiPackage.set_impact_percentiles --no-rq --limit=100000 


heroku run --size=performance-l python update.py Person.set_scores --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Person.set_subscore_percentiles --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Person.set_impact --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Person.set_impact_percentiles --no-rq --limit=1000000 --chunk=100
