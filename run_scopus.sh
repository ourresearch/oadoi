#!/bin/bash
# dyno number avail in $DYNO as per http://stackoverflow.com/questions/16372425/can-you-programmatically-access-current-heroku-dyno-id-name/16381078#16381078

for ((i=1; i<=$SCOPUS_WORKERS; i++))
do
  COMMAND="python scopus_worker.py celery worker -n scopus-$DYNO:${i} " 
  echo $COMMAND
  $COMMAND&
done
trap "kill 0" SIGINT SIGTERM EXIT
wait
