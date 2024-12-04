#!/bin/bash
# dyno number avail in $DYNO as per http://stackoverflow.com/questions/16372425/can-you-programmatically-access-current-heroku-dyno-id-name/16381078#16381078

COMMAND="python queue_repo.py --run --id ca8f8d56758a80a4f86"
echo $COMMAND
$COMMAND&
trap "kill 0" INT TERM EXIT
wait
