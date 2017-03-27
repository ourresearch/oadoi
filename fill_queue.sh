#!/bin/bash
trap "exit" INT

python update.py Crossref.run_if_open --limit=1000 --rq
for (( i=1; i <= 1000000; i++ ))
do
    echo "loop $i"
    python update.py Crossref.run_if_open --limit=1000 --rq --append
done





#python update.py Crossref.run --limit=10000 --chunk=10 --rq
#python update.py Crossref.run --limit=100000 --chunk=10 --rq --append
#python update.py Crossref.run --limit=100000 --chunk=10 --rq --append

#python update.py Crossref.run --limit=10000 --chunk=250 --rq
#python update.py Crossref.run --limit=100000 --chunk=250 --rq --append
#python update.py Crossref.run --limit=100000 --chunk=250 --rq --append
