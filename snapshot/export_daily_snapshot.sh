#!/bin/bash

#
# Bash script to export snapshot of unpaywall data
#

usage() {
    echo "
Usage: $0
Export a whole snapshot from database to S3

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
    AWS_PROFILE_OPT=" --profile=$AWS_PROFILE_EXPORT "
else
    AWS_PROFILE_OPT=""
fi

TODAY_FOR_FILE=$(date --utc +'%Y-%m-%dT%H%M%S' )

PROCESS="export_snapshot"
FILENAME="unpaywall_snapshot_${TODAY_FOR_FILE}.jsonl"

logger "Process  : $PROCESS"
logger "Filename : $FILENAME"

logger "Exporting database column to file"
/usr/bin/psql "${DATABASE_URL}?ssl=true" -c "\copy (select response_jsonb from pub where response_jsonb is not null and response_jsonb->>'oa_status' is not null) to '${FILENAME}';"
PSQL_EXIT_CODE=$?

if [[ $PSQL_EXIT_CODE -ne 0 ]] ; then
    logger "Error ${PSQL_EXIT_CODE} while running psql"
    exit 2
fi

# this is sometimes used for debugging, comment the above out when you do it
# logger "Using filename already given"
# FILENAME="unpaywall_snapshot_2018-03-29T113154.jsonl"

logger "Created $FILENAME: $(stat -c%s """$FILENAME""") bytes"

logger "Cleaning, fixing bad characters, and compressing"
sed '/^\s*$/d' "$FILENAME" | sed 's:\\\\:\\:g' | /bin/gzip -9 -c - > "$FILENAME.gz"

GZIP_EXIT_CODE=$?
if [[ $GZIP_EXIT_CODE -ne 0 ]] ; then
    logger "Error ${GZIP_EXIT_CODE} while running gzip"
    exit 3
fi
logger "Created archive $FILENAME.gz: $(stat -c%s """$FILENAME.gz""") bytes"

SNAPSHOT_BUCKET=unpaywall-daily-snapshots

logger "Uploading snapshot to s3://${SNAPSHOT_BUCKET}"
aws s3 cp --no-progress $AWS_PROFILE_OPT "${FILENAME}.gz" "s3://${SNAPSHOT_BUCKET}/${FILENAME}.gz"
S3CP_EXIT_CODE=$?
if [[ $S3CP_EXIT_CODE -ne 0 ]] ; then
    logger "Error ${S3CP_EXIT_CODE} while uploading export"
    exit 4
fi

logger "enumerating snapshots"
snapshots=($(aws s3 $AWS_PROFILE_OPT  ls s3://${SNAPSHOT_BUCKET} | sed -r 's/.*(unpaywall_snapshot_.*\.jsonl\.gz).*/\1/' | sort))
S3LS_EXIT_CODE=$?
if [[ $S3LS_EXIT_CODE -ne 0 ]]; then
    logger "error ${S3LS_EXIT_CODE} listing snapshots"
    exit 5
fi

# delete all but most recent 2 snapshots
if [[ ${#snapshots[@]} -gt 2 ]]; then
    for snapshot in "${snapshots[@]:0:${#snapshots[@]}-2}"; do
        logger "deleting $snapshot"
        aws s3 rm $AWS_PROFILE_OPT "s3://${SNAPSHOT_BUCKET}/${snapshot}"
        S3RM_EXIT_CODE=$?
        if [[ $S3RM_EXIT_CODE -ne 0 ]]; then
            logger "error ${S3RM_EXIT_CODE} deleting old snapshot $snapshot"
            exit 6
        fi
    done
fi

rm "${FILENAME}"
rm "${FILENAME}.gz"

logger "Done"