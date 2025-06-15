import boto3


def get_daily_snapshot_key():
    s3 = boto3.client('s3')
    bucket_name = 'unpaywall-data-feed-walden'
    directory = 'full_snapshots'

    try:
        response = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix=f'{directory}/'
        )

        if 'Contents' not in response:
            return None

        # Filter for snapshot files and sort by last modified date
        snapshot_files = [
            obj for obj in response['Contents']
            if obj['Key'].endswith('.jsonl.gz') and 'unpaywall_snapshot_' in obj['Key']
        ]

        if not snapshot_files:
            return None

        latest_snapshot = sorted(snapshot_files, key=lambda x: x['LastModified'], reverse=True)[0]

        return latest_snapshot['Key']

    except Exception as e:
        print(f"Error getting latest snapshot: {e}")
        return None