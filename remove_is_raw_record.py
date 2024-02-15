import argparse
import traceback

from sqlalchemy import text

from app import oa_db_engine
from util import chunks


def parse_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--start_index', '-i',
                            default=0,
                            type=int, help='')
    return arg_parser.parse_args()


args = parse_args()

with oa_db_engine.connect() as db_conn:
    print(f'[*] Fetching raw record marker IDs...')
    all_records = db_conn.execute(
        "SELECT id FROM ins.recordthresher_record WHERE authors LIKE '%is_raw_record%'").fetchall()
    all_records = [record[0] for record in all_records[args.start_index:]]
    page = 0
    chunk_size = 10_000
    print(f'[*] Removing raw record marker from {len(all_records)} records...')
    for i, chunk in enumerate(chunks(all_records, chunk_size)):
        try:
            db_conn.execute(text(
                '''UPDATE ins.recordthresher_record SET authors = json_remove_array_element(authors::json, '{"is_raw_record": true}') WHERE id IN :chunk'''),
                {'chunk': tuple(chunk)})
            page += 1
            db_conn.connection.commit()
            print(
                f'[*] Removed raw record marker from {page * chunk_size}/{len(all_records)} records')
        except Exception as e:
            print(f'[!] Error updating chunk')
            traceback.print_exc()
