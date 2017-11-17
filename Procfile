web: gunicorn views:app -w 3 --timeout 60 --reload
update: bash run_worker.sh
run_with_hybrid: bash run_hybrid_worker.sh
update_dates: bash run_dates_worker.sh
run_pmh: bash run_pmh.sh
run_repo: bash run_repo.sh
base_find_fulltext: python update.py Base.find_fulltext --chunk=25 --limit=10000000
crossref_get_api: bash run_dates_worker.sh
load_test: python load_test.py --limit=50000
