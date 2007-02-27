# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import sys

from test_dialback_reply_active import TestDialbackReplyActive

DEBUG=True

class TestDialbackReplyActive2(TestDialbackReplyActive):
    """  
    Testing DIALBACK_REPLY message of Dialback extension V1 

    This test checks how the Tribler code responds to good and bad 
    DIALBACK_REPLY messages. I.e. the Tribler client initiates
    the dialback by connecting to us and sending a DIALBACK_REQUEST and we
    reply with good and bad messages.

    This test does NOT allow authoritative answers from superpeers.
    """

    def setUpPreTriblerInit(self):
        """ override TestDialbackReplyActive """
        self.NLISTENERS=4 # Must be same as DialbackMsgHandler PEERS_TO_AGREE
        TestDialbackReplyActive.setUpPreTriblerInit(self)
        self.config['dialback_trust_superpeers'] = 0


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. SuperPeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_dra2.py <method name>"
    else:
        suite.addTest(TestDialbackReplyActive2(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])
    
