from app import oa_db_engine
from util import chunks

with oa_db_engine.connect() as db_conn:
    all_records = db_conn.execute('SELECT id FROM public.tmp_rorr_marked_raw_records').fetchall()
    all_records = [record[0] for record in all_records]
    page = 1
    chunk_size = 10_000
    for i, chunk in enumerate(chunks(all_records, chunk_size)):
        db_conn.execute('''UPDATE ins.recordthresher_record SET authors = json_remove_array_element(authors::json, '{"is_raw_record": true}') WHERE id IN :chunk''', (tuple(chunk), ))
        page += 1
        print(f'[*] Removed raw record marker from {page*chunk_size}/{len(all_records)} records')