# long web timeout value needed to facilitate proxy of s3 changefile content
# setting to 10 hours: 60*60*10=36000
web: gunicorn views:app -w $WEB_WORKERS_PER_DYNO --timeout 36000 --reload
web_dev: gunicorn views:app -w 2 --timeout 36000 --reload
update: bash run_worker.sh
refresh: bin/start-pgbouncer bash run_hybrid_worker.sh
refresh_aux: bin/start-pgbouncer bash run_hybrid_worker_aux_0.sh
run_pmh: bash run_pmh.sh
run_repo: bash run_repo.sh
run_page: bash run_page.sh
run_pdf_url_check: bin/start-pgbouncer bash run_pdf_url_check.sh
green_scrape: bash run_green_scrape_worker.sh
publisher_scrape: bash run_publisher_scrape_worker.sh
repo_oa_location_export: python repo_oa_location_export.py
pubmed_record_queue: bash run_pubmed_record_worker.sh
pmh_rt_record_queue: bash run_pmh_rt_record_worker.sh
doi_rt_record_queue: bash run_doi_rt_record_worker.sh
recordthresher_refresh: bash run_recordthresher_refresh_worker.sh
rescrape_iop: python3 scrape_publisher.py -n 50 -r -f type:journal-article,has_doi:true,has_raw_affiliation_string:false,publication_date:>2015-01-01,primary_location.source.host_organization:P4310320083
rescrape_elsevier: python3 scrape_publisher.py -n 50 -r -f type:journal-article,has_doi:true,has_raw_affiliation_string:false,publication_date:>2015-01-01,primary_location.source.host_organization:P4310320990