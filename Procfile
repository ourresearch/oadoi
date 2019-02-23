# long web timeout value needed to facilitate proxy of s3 changefile content
# setting to 10 hours: 60*60*10=36000
web: gunicorn views:app -w 5 --timeout 36000 --reload
update: bash run_worker.sh
refresh: bin/start-pgbouncer-stunnel bash run_hybrid_worker.sh
run_date_range: bash run_dates_worker.sh
run_pmh: bash run_pmh.sh
run_repo: bash run_repo.sh
run_page: bash run_page.sh
run_pdf_check: bin/start-pgbouncer-stunnel bash run_pdf_check.sh
run_pdf_url_extract: bash run_pdf_url_extract.sh
heather_test: python queue_page.py --method=set_version_and_license --run --chunk=100
