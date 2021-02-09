# long web timeout value needed to facilitate proxy of s3 changefile content
# setting to 10 hours: 60*60*10=36000
web: gunicorn views:app -w $WEB_WORKERS_PER_DYNO --timeout 36000 --reload
web_dev: gunicorn views:app -w 2 --timeout 36000 --reload
update: bash run_worker.sh
refresh: bin/start-pgbouncer bash run_hybrid_worker.sh
refresh_aux: bin/start-pgbouncer bash run_hybrid_worker_aux_0.sh
refresh_aux_1: bin/start-pgbouncer bash run_hybrid_worker_aux_1.sh
run_date_range: bash run_dates_worker.sh
run_pmh: bash run_pmh.sh
run_repo: bash run_repo.sh
run_page: bash run_page.sh
run_pdf_url_check: bin/start-pgbouncer bash run_pdf_url_check.sh
green_scrape: bash run_green_scrape_worker.sh
publisher_scrape: bash run_publisher_scrape_worker.sh
heather_test: python queue_page.py --method=set_version_and_license --run --chunk=100
