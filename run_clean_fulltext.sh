for (( i=1; i<=$CLEAN_FULLTEXT_WORKERS_PER_DYNO; i++ ))
do
  COMMAND="python clean_fulltext.py"
  echo $COMMAND
  $COMMAND &
done
trap "kill 0" INT TERM EXIT
wait
