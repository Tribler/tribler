#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=../..:"$PYTHONPATH"
export PYTHONPATH
python test_channelcast.py test_channel_subscription
python test_channelcast.py test_channelcast
python test_channelcast.py test_channel_query
python test_channelcast.py test_channel_update
python test_channelcast.py test_channel_votecast
