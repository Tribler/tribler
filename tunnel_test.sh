#!/bin/bash

function killstuff {
	echo -e "\nKilling all jobs"
	jobs -p | xargs kill
	exit 0
}

trap killstuff SIGINT

PYTHONPATH=.:"$PYTHONPATH"
export PYTHONPATH

python -OO Tribler/AnonTunnel/Main.py --cmd=1081 > /dev/null 2>&1 &
PID_TUNNEL1=$!
echo "Starting first tunnel node, pid $PID_TUNNEL1"

python -OO Tribler/AnonTunnel/Main.py --cmd=1082 > /dev/null 2>&1 &
PID_TUNNEL2=$!
echo "Starting second tunnel node, pid $PID_TUNNEL2"

cd ../libswift
rm 79* -f

./swift -f u2.sql -l 0.0.0.0:20000 > /dev/null 2>&1 &
PID_SEEDER=$!
echo "Starting swift SEEDER, pid $PID_SEEDER"

echo "Waiting for 20 seconds for the circuits to be made"
sleep 20
echo "Starting swift LEECHER"
./swift -h 7968deb036fcb297b437d92919d4649f6955bbd0 -t 127.0.0.1:20000 -S 127.0.0.1:1080 -p


