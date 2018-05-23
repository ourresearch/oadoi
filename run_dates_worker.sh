#!/bin/bash
# dyno number avail in $DYNO as per http://stackoverflow.com/questions/16372425/can-you-programmatically-access-current-heroku-dyno-id-name/16381078#16381078

for (( i=1; i<=1; i++ ))
do
  COMMAND="python queue_date_range.py --run"
  echo $COMMAND
  $COMMAND&
done
trap "kill 0" INT TERM EXIT
wait
