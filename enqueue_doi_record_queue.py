import os
import traceback
from datetime import timedelta

import pandas as pd

from sqlalchemy import create_engine, text, bindparam

OPENALEX_DB_URL = os.getenv('OPENALEX_DATABASE_URL').replace('postgres://',
                                                             'postgresql://')
OADOI_DB_URL = os.getenv('DATABASE_URL').replace('postgres://', 'postgresql://')

OPENALEX_DB_ENGINE = create_engine(OPENALEX_DB_URL).execution_options(
    isolation_level='AUTOCOMMIT')
OADOI_DB_ENGINE = create_engine(OADOI_DB_URL)

SELECT_CMD = "WITH chunk as (SELECT * FROM recordthresher.doi_record_add_everything_queue WHERE enqueued_add_everything = false) UPDATE recordthresher.doi_record_add_everything_queue tbl SET enqueued_add_everything = true FROM chunk WHERE tbl.doi = chunk.doi RETURNING chunk.doi, chunk.real_updated;"


def date_transform_func(real_updated):
    date = real_updated + timedelta(days=365 * 30)
    return date.isoformat().replace('T', ' ')


def main():
    with OADOI_DB_ENGINE.connect() as conn:
        ROWS = conn.execute(text(SELECT_CMD)).fetchall()
        conn.connection.commit()

    with OPENALEX_DB_ENGINE.connect() as conn, conn.connection.cursor() as oa_cur:
        df = pd.DataFrame(data=ROWS)
        dois = tuple(df['doi'].tolist())
        work_ids_stmnt = text(
            'SELECT work_id, doi FROM ins.recordthresher_record WHERE doi IN :dois').bindparams(
            bindparam('dois', expanding=True))
        work_ids = conn.execute(work_ids_stmnt, {'dois': dois}).fetchall()
        df2 = pd.DataFrame(data=work_ids)
        df = df.merge(df2, on=['doi'])
        df['real_updated'] = df['real_updated'].apply(date_transform_func)
        df.drop(columns=['doi'], inplace=True)
        df = df[['work_id', 'real_updated']]
        rows = list(df.itertuples(index=False, name=None))
        rows_tup_formatted = ', '.join(
            [oa_cur.mogrify('(%s, %s)', row).decode() for row in rows])
        insert_stmnt = text(
            f'INSERT INTO queue.run_once_work_add_everything (work_id, work_updated) VALUES {rows_tup_formatted} ON CONFLICT DO NOTHING;')
        conn.execute(insert_stmnt)
        conn.connection.commit()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(traceback.format_exc())
        print(e)
