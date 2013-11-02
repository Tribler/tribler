#!/bin/sh
# Run Tribler from source tree

PYTHONPATH=.:"$PYTHONPATH"
export PYTHONPATH

let END=$1 i=1
while ((i<=END)); do
	python -OO Tribler/community/anontunnel/Main.py &
	
	let i++
done
