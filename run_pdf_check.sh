#!/bin/bash

for (( i=1; i<=2; i++ ))
do
  COMMAND="python queue_pdf_url_check.py --run"
  echo $COMMAND
  $COMMAND&
done
trap "kill 0" INT TERM EXIT
wait
