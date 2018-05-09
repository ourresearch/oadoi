# long web timeout value needed to facilitate proxy of s3 changefile content
# setting to 10 hours: 60*60*10=36000
web: bin/start-pgbouncer-stunnel gunicorn views:app -w 5 --timeout 36000 --reload
update: bin/start-pgbouncer-stunnel bash run_worker.sh
refresh: bin/start-pgbouncer-stunnel bash run_hybrid_worker.sh
run_date_range: bin/start-pgbouncer-stunnel bash run_dates_worker.sh
run_pmh: bin/start-pgbouncer-stunnel bash run_pmh.sh
run_repo: bin/start-pgbouncer-stunnel bash run_repo.sh
run_page: bin/start-pgbouncer-stunnel bash run_page.sh
