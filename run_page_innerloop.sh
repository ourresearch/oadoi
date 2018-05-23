#!/bin/bash
# dyno number avail in $DYNO as per http://stackoverflow.com/questions/16372425/can-you-programmatically-access-current-heroku-dyno-id-name/16381078#16381078

trap "kill 0" INT TERM EXIT SIGINT SIGTERM
while [ 1 ]
do
  python queue_page.py --run --chunk=2 --noloop || break 2
done
