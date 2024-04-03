#!/bin/bash
for (( i=1; i<=$DOI_RT_RECORD_WORKERS_PER_DYNO; i++ ))
do
  COMMAND="python queue_datacite_doi.py --chunk=$DOI_RT_RECORD_CHUNK_SIZE"
  echo $COMMAND
  $COMMAND &
done
trap "kill 0" INT TERM EXIT
wait
