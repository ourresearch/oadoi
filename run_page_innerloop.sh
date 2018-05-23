#!/bin/bash
# dyno number avail in $DYNO as per http://stackoverflow.com/questions/16372425/can-you-programmatically-access-current-heroku-dyno-id-name/16381078#16381078

while [ 1 ]
do
  COMMAND="python queue_page.py --run --chunk=10 --noloop"
  echo $COMMAND
  $COMMAND
done
trap "kill 0" INT TERM EXIT
wait
