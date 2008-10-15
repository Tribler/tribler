#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=../..:"$PYTHONPATH"
export PYTHONPATH

# python test_friendship.py singtest_good_friendship_req0
# python test_friendship.py singtest_good_friendship_req1
# python test_friendship.py singtest_good_friendship_he_invites
python test_friendship.py singtest_good_friendship_req1_send_social_overlap
# python test_friendship.py singtest_good_friendship_he_already_invited
# python test_friendship.py singtest_good_friendship_fwd_req_dest3rdp
# python test_friendship.py singtest_good_friendship_fwd_resp0_dest3rdp
# python test_friendship.py singtest_good_friendship_fwd_resp1_dest3rdp
# python test_friendship.py singtest_good_friendship_fwd_req_desthim
# python test_friendship.py singtest_good_friendship_fwd_resp0_desthim
# python test_friendship.py singtest_good_friendship_fwd_resp1_desthim
# python test_friendship.py singtest_good_friendship_delegate_req
# python test_friendship.py singtest_good_friendship_delegate_shutdown
# python test_friendship.py singtest_bad_all
