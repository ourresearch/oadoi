#!/bin/bash

#
# Bash script to export daily changefiles of unpaywall data
#

usage() {
    echo "
Usage: $0
Export a daily changefile from database to S3

The following environmental variables are required:

DATABASE_URL     connection string for database
Requires a properly configured aws cli to allow S3 upload.

"
}

logger() {
    echo "$(date --utc +'%Y-%m-%dT%H:%M:%S') : $1"
}

if [[ "$DATABASE_URL" == "" ]]; then
    echo "Missing DATABASE_URL environment variable"
    usage
    exit 1
fi

if [[ "$AWS_PROFILE_EXPORT" != "" ]]; then
    AWS_CP_CMD="/usr/bin/aws s3 cp --profile=$AWS_PROFILE_EXPORT "
else
    AWS_CP_CMD="/usr/bin/aws s3 cp "
fi

JSON_STAGING_TABLE=daily_export_staging
DAILY_EXPORT_HISTORY=daily_export_dates
TODAY_FOR_FILE=$(date --utc +'%Y-%m-%dT%H%M%S' )

export_file() {
    BUCKET="unpaywall-daily-data-feed"
    FILENAME="changed_dois_with_versions_${TODAY_FOR_FILE}.jsonl"

    logger "Filename : $FILENAME"

    logger "Exporting view to file json"
    /usr/bin/psql "${DATABASE_URL}" -c "\copy (select response_jsonb from $JSON_STAGING_TABLE where response_jsonb is not null) to '${FILENAME}';"
    PSQL_EXIT_CODE=$?

    if [[ $PSQL_EXIT_CODE -ne 0 ]] ; then
        logger "Error ${PSQL_EXIT_CODE} while running psql"
        exit 2
    fi
    logger "Created $FILENAME: $(stat -c%s """$FILENAME""") bytes"
    logger "wc on $FILENAME: $(wc -l < """$FILENAME""") lines"

    logger "Cleaning, fixing bad characters"
    sed -i '/^\s*$/d' "$FILENAME"
    sed -i 's:\\\\:\\:g' "$FILENAME"

    logger "Compressing"
    /bin/gzip -9 -c "$FILENAME" > "$FILENAME.gz"
    GZIP_EXIT_CODE=$?
    if [[ $GZIP_EXIT_CODE -ne 0 ]] ; then
        logger "Error ${GZIP_EXIT_CODE} while running gzip"
        exit 3
    fi
    logger "Created archive $FILENAME.gz: $(stat -c%s """$FILENAME.gz""") bytes"

    logger "Uploading export"
    UPDATED=$(date --utc +'%Y-%m-%dT%H:%M:%S')
    LINES=$(wc -l < $"""$FILENAME""")
    $AWS_CP_CMD "$FILENAME.gz" "s3://$BUCKET/$FILENAME.gz" --metadata """lines=$LINES,updated='$UPDATED'"""
    S3CP_EXIT_CODE=$?
    if [[ $S3CP_EXIT_CODE -ne 0 ]] ; then
        logger "Error ${S3CP_EXIT_CODE} while uploading export"
        exit 5
    fi
    logger "Done"
    logger "***"
    logger ""
}

logger "extracting possible changes for export"

/usr/bin/psql "${DATABASE_URL}" <<SQL
    begin;

    truncate $JSON_STAGING_TABLE;

    insert into $JSON_STAGING_TABLE (
        select pub.id, pub.updated, pub.last_changed_date, pub.response_jsonb
        from pub left join $DAILY_EXPORT_HISTORY history using (id)
        where pub.last_changed_date between now() - '2 days'::interval and now()
        and pub.updated > '1043-01-01'::timestamp
        and (history.last_exported_update is null or history.last_exported_update < pub.last_changed_date)
    );

    commit;
SQL

export_file

logger "updating last-exported dates"

/usr/bin/psql "${DATABASE_URL}" <<SQL
    insert into $DAILY_EXPORT_HISTORY (id, last_exported_update) (
        select id, last_changed_date from $JSON_STAGING_TABLE
    ) on conflict (id) do update set last_exported_update = excluded.last_exported_update;

    truncate $JSON_STAGING_TABLE;
SQL

/usr/local/bin/heroku run -a oadoi python cache_changefile_dicts.py