web: gunicorn views:app -w 3 --timeout 60 --reload
update: bin/start-pgbouncer-stunnel bash run_worker.sh
refresh: bin/start-pgbouncer-stunnel bash run_hybrid_worker.sh
run_date_range: bin/start-pgbouncer-stunnel bash run_dates_worker.sh
run_pmh: bin/start-pgbouncer-stunnel bash run_pmh.sh
run_repo: bin/start-pgbouncer-stunnel bash run_repo.sh
run_page: bin/start-pgbouncer-stunnel bash run_page.sh
