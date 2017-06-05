web: gunicorn views:app -w 3 --timeout 60 --reload
run: python update.py Crossref.run --chunk=100 --limit=900000000
run_with_hybrid: python update.py Crossref.run_with_hybrid --chunk=5 --limit=100000000
base_find_fulltext: python update.py Base.find_fulltext --chunk=25 --limit=10000000
skip_all_hybrid: python update.py Crossref.run_with_skip_all_hybrid --chunk=10 --limit=100000000
load_test: python load_test.py --limit=50000
