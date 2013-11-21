#!/bin/bash

NUM_HOPS=$1

UDP_IP="127.0.0.1"
UDP_PORT=1081

SWIFT_SEED="95.211.198.140:21000"
SWIFT_ROOTHASH="dbd61fedff512e19b2a6c73b8b48eb01c9507e95"
export PYTHONPATH=.:"$PYTHONPATH"

rm $SWIFT_ROOTHASH*

# Kill all background jobs when we press CTRL-C or sent an SIGINT
function kill_all_jobs { jobs -p | xargs kill -9; exit 0; }
trap kill_all_jobs SIGINT

# start tunnel
python Tribler/community/anontunnel/Main.py -c $UDP_PORT -l constant $NUM_HOPS -s length $NUM_HOPS $NUM_HOPS --socks5 1080 &
TUNNEL_PID=$!

# start swift
./swift --proxy 127.0.0.1:1080 -h $SWIFT_ROOTHASH -t $SWIFT_SEED -p

# Get Stats
python Tribler/community/anontunnel/scripts/get_stats.py > output/stats.json

# Wait till others finish experiment
sleep 10

# Sent the STOP signal
python Tribler/community/anontunnel/scripts/stop.py