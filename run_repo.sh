#!/bin/bash
# dyno number avail in $DYNO as per http://stackoverflow.com/questions/16372425/can-you-programmatically-access-current-heroku-dyno-id-name/16381078#16381078

for (( i=1; i<=2; i++ ))
do
   COMMAND="python queue_repo.py --run"
#   COMMAND="python queue_repo.py --run --method=set_identify_and_initial_query --chunk=10"
  echo $COMMAND
  $COMMAND&
done
trap "kill 0" INT TERM EXIT
wait
