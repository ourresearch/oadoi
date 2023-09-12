import tarfile
import json
import psycopg2
import os


""""
Use this script to stage the Crossref snapshot data in a PostgreSQL database. Designed to run on an EC2 instance.

1. Save the Crossref snapshot tar.gz file to an EC2 instance with:
    curl -H 'crossref-api-key: mykey' -H 'User-Agent: Downloader/1.1 (mailto:dev@ourresearch.org)' -v -L -o all.json.tar.gz -X GET https://api.crossref.org/snapshots/monthly/latest/all.json.tar.gz
2. Create a temp table to hold the data:
    CREATE TABLE IF NOT EXISTS temp_crossref_monthly_sync (
        id TEXT PRIMARY KEY,
        response_jsonb JSONB
        processed BOOLEAN DEFAULT FALSE
    );
    CREATE INDEX idx_temp_crossref_monthly_sync_processed ON temp_crossref_monthly_sync(processed) WHERE processed = FALSE;
3. Run this script to dump each JSON line into the temp table:
    python crossref_snapshot_setup.py
"""


def read_json_records_from_tar_gz_stream(file_path, batch_size=5000):
    with tarfile.open(file_path, mode='r|gz') as tar:
        for tarinfo in tar:
            if tarinfo.isfile() and tarinfo.name.endswith('.json'):
                print(f"Processing {tarinfo.name}")
                file_content = tar.extractfile(tarinfo).read()
                json_content = json.loads(file_content)

                items = json_content.get('items', [])

                for i in range(0, len(items), batch_size):
                    yield items[i:i + batch_size]


def process_batch(batch, conn):
    cursor = conn.cursor()
    insert_sql = """
        INSERT INTO temp_crossref_monthly_sync (response_jsonb)
        VALUES %s
    """

    # Prepare the batch data
    batch_data = [(json.dumps(record),) for record in batch]

    # Use psycopg2's `extras` to execute a batch insert
    from psycopg2 import extras
    extras.execute_values(cursor, insert_sql, batch_data)

    conn.commit()
    cursor.close()


def main():
    # Establish connection to PostgreSQL
    conn = psycopg2.connect(os.getenv('UNPAYWALL_DB'))

    # Set the path to the local tar.gz file
    local_path = os.path.expanduser('~/crossref/august_2023.json.tar.gz')

    # Iterate over records in batches
    for batch in read_json_records_from_tar_gz_stream(local_path):
        process_batch(batch, conn)

    conn.close()


if __name__ == "__main__":
    main()
