#!/bin/bash

for (( i=1; i<=$CROSSREF_SNAPSHOT_SYNC_WORKERS_PER_DYNO; i++ ))
do
  COMMAND="python crossref_snapshot_sync.py"
  echo $COMMAND
  $COMMAND &
done
trap "kill 0" INT TERM EXIT
wait
