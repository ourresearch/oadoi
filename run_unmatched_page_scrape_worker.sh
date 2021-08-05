#!/bin/bash

for (( i=1; i<=$UNMATCHED_PAGE_SCRAPE_WORKERS_PER_DYNO; i++ ))
do
  COMMAND="python queue_unmatched_repo_page_scrape.py --run"
  echo $COMMAND
  $COMMAND&
done
trap "kill 0" INT TERM EXIT
wait
