# long web timeout value needed to facilitate proxy of s3 changefile content
# setting to 10 hours: 60*60*10=36000
web: gunicorn views:app -w $WEB_WORKERS_PER_DYNO --timeout 36000 --reload
web_dev: gunicorn views:app -w 2 --timeout 36000 --reload
update: bash run_worker.sh
refresh: bin/start-pgbouncer-stunnel bash run_hybrid_worker.sh
refresh_aux: bin/start-pgbouncer-stunnel bash run_hybrid_worker_aux_0.sh
run_pmh: bash run_pmh.sh
run_repo: bash run_repo.sh
run_pdf_url_check: bin/start-pgbouncer-stunnel bash run_pdf_url_check.sh
green_scrape: bash run_green_scrape_worker.sh
publisher_scrape: bash run_publisher_scrape_worker.sh
repo_oa_location_export: python repo_oa_location_export.py
pubmed_record_queue: bash run_pubmed_record_worker.sh
pmh_rt_record_queue: bash run_pmh_rt_record_worker.sh
doi_rt_record_queue: bash run_doi_rt_record_worker.sh
recordthresher_refresh: bash run_recordthresher_refresh_worker.sh
recordthresher_refresh_enqueue_top_25: bash run_recordthresher_refresh_enqueue_top_25.sh
recordthresher_refresh_enqueue_tmp: python3 recordthresher_refresh.py  -ep https://openalex.org/P4310320527 -ep https://openalex.org/P4310319811 -ep https://openalex.org/P4310320448 -ep https://openalex.org/P4310319748 -ep https://openalex.org/P4310319847 -ep https://openalex.org/P4310317825 -ep P4310320990 -ep P4310320083
download_pdfs: python3 download_pdfs.py -dt 25