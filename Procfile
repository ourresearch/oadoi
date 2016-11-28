web: gunicorn views:app -w 3 --timeout 60 --reload
RQ_worker_queue_0: python rq_worker.py 0
RQ_worker_queue_1: python rq_worker.py 1
base: python update_base_in_elastic.py
crossref: python update_crossref_in_elastic.py