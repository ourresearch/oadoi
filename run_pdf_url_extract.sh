#!/bin/bash

for (( i=1; i<=$PDF_URL_EXTRACT_PROCS_PER_DYNO; i++ ))
do
  COMMAND="python queue_pdf_url_extract.py --run --chunk=$PDF_URL_EXTRACT_CHUNK_SIZE"
  echo $COMMAND
  $COMMAND&
done
trap "kill 0" INT TERM EXIT
wait
