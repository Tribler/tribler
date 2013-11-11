#!/bin/bash
UDP_IP="127.0.0.1"
UDP_PORT=1081

SWIFT_SEED="95.211.198.140:21000"
SWIFT_ROOTHASH="dbd61fedff512e19b2a6c73b8b48eb01c9507e95"
export PYTHONPATH=.:"$PYTHONPATH"

# Kill all background jobs when we are done
function kill_all_jobs { jobs -p | xargs kill -9; exit 1; }
trap kill_all_jobs SIGINT

# start tunnel
python Tribler/community/anontunnel/Main.py -c $UDP_PORT &
TUNNEL_PID=$!

# start swift
./swift --proxy 127.0.0.1:1080 -h $SWIFT_ROOTHASH -t $SWIFT_SEED -p

# Get Stats
python Tribler/community/anontunnel/scripts/get_stats.py


# Wait till experiment is finished
python Tribler/community/anontunnel//scripts/stop.py