#!/bin/bash
# dyno number avail in $DYNO as per http://stackoverflow.com/questions/16372425/can-you-programmatically-access-current-heroku-dyno-id-name/16381078#16381078

for (( i=1; i<=2; i++ ))
do
#  COMMAND="python update.py DateRange.get_unpaywall_events --chunk=1 --limit=100000000 --name=hybrid-$DYNO:${i} "
  COMMAND="python update.py DateRange.get_oaipmh_events --chunk=100 --limit=100000000 --name=hybrid-$DYNO:${i} "
  echo $COMMAND
  $COMMAND&
done
trap "kill 0" INT TERM EXIT
wait
