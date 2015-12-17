heroku run --size=performance-l python update.py Package.dedup_people --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Package.dedup_special_cases --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Package.set_credit --no-rq --limit=1000000 --chunk=100

heroku run --size=performance-l python update.py Person.set_scores --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Person.set_subscore_percentiles --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Person.set_impact --no-rq --limit=1000000 --chunk=100
heroku run --size=performance-l python update.py Person.set_impact_percentiles --no-rq --limit=1000000 --chunk=100
