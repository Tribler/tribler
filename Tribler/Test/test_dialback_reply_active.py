# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest
import os
import sys
import time
import socket
import tempfile

from M2Crypto import EC
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import DIALBACK_REQUEST, DIALBACK_REPLY, getMessageName
from Tribler.Core.Utilities.utilities import show_permid
from Tribler.Core.NATFirewall.ReturnConnHandler import dialback_infohash

from btconn import BTConnection
from olconn import OLConnection
from Tribler.Test.test_as_server import TestAsServer

DEBUG=True

REPLY_IP='127.0.0.10'


class TestDialbackReplyActive(TestAsServer):

    """  
    Testing DIALBACK_REPLY message of Dialback extension V1 

    This test checks how the Tribler code responds to good and bad 
    DIALBACK_REPLY messages. I.e. the Tribler client initiates
    the dialback by connecting to us and sending a DIALBACK_REQUEST and we
    reply with good and bad messages.

    This test allows authoritative answers from superpeers.

    WARNING: Each of the test_ methods should be tested by running the TestCase 
    in a separate Python interpreter to prevent problems with our singleton 
    classes, e.g. SuperPeerDB, etc.
    """

    def setUp(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: Setup"
        self.NLISTENERS=1
        TestAsServer.setUp(self)

    def setUpPreSession(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: Pre Tribler Init"
        TestAsServer.setUpPreSession(self)
        print >> sys.stderr,"test: Pre Tribler Init: config_path",self.config_path
        # Enable dialback support
        self.config.set_dialback(True)
        self.config.set_buddycast(True) # make sure overlay connections are being made
        self.config.set_start_recommender(True)

        # Write superpeers.txt
        self.install_path = tempfile.mkdtemp()
        spdir = os.path.join(self.install_path, 'Tribler', 'Core')
        os.makedirs(spdir)
        superpeerfilename = os.path.join(spdir, 'superpeer.txt')
        print >> sys.stderr,"test: writing",self.NLISTENERS,"superpeers to",superpeerfilename
        f = open(superpeerfilename, "w")

        self.mylistenport = []
        self.myss = []
        self.mykeypairs = []
        self.mypermids = []
        for i in range(self.NLISTENERS):
            # Start our server side, to with Tribler will try to connect
            self.mylistenport.append(4810+i)
            self.myss.append(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            self.myss[i].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.myss[i].bind(('', self.mylistenport[i]))
            self.myss[i].listen(1)

            self.mykeypairs.append(EC.gen_params(EC.NID_sect233k1))
            self.mykeypairs[i].gen_key()
            self.mypermids.append(str(self.mykeypairs[i].pub().get_der()))

            content = '127.0.0.1, '+str(self.mylistenport[i])+', '+show_permid(self.mypermids[i])+', FakeSuperPeer\n'
            f.write(content)
        f.close()
        
        self.config.set_install_dir(self.install_path)

        """
        # To avoid errors
        cfilename = os.path.join(self.install_path, 'category.conf')
        f = open(cfilename, "wb")
        f.write('')
        f.close()
        """
        
    def setUpPostSession(self):
        """ override TestAsServer """
        TestAsServer.setUpPostSession(self)
        
        self.myoriginalip = self.session.get_external_ip()

    def tearDown(self):
        """ override TestAsServer """
        print >> sys.stderr,"test: *** TEARDOWN"
        TestAsServer.tearDown(self)

        for i in range(self.NLISTENERS):
            self.myss[i].close()
        # risky: remove self.install_path which was overridden

    #
    # Good DIALBACK_REQUEST, builds on TestDialbackReply code
    #    
    def singtest_good_dreply(self):
        self._test_dreply(self.create_good_dreply,True)

    #
    # Bad DIALBACK_REQUEST, builds on TestDialbackReply code
    #    
    def singtest_bad_not_bdecodable(self):
        print >>sys.stderr,"test: *** NOT DECODABLE TEST"
        self._test_dreply(self.create_not_bdecodable,False)

    def singtest_bad_not_string(self):
        self._test_dreply(self.create_not_string,False)

    def singtest_bad_not_validip(self):
        self._test_dreply(self.create_not_validip,False)

    def singtest_bad_diff_ips(self):
        self._test_dreply(self.create_diff_ips,False,diff_ips_test=True) # just semantically bad


    ### TODO: send different valid answers so consensus not reached

    #
    # Main test code
    #
    def _test_dreply(self,gen_dreply,good,diff_ips_test=False):
        for i in range(self.NLISTENERS):
            print >> sys.stderr,"test: waiting for #",i,"listenport",self.mylistenport[i]
            conn, addr = self.myss[i].accept()
            s = OLConnection(self.mykeypairs[i],'',0,conn,self.mylistenport[i])
            while True:
                msg = s.recv()
                self.assert_(len(msg) > 0)
                print >> sys.stderr,"test: Received overlay message",getMessageName(msg[0])
                if msg[0] == DIALBACK_REQUEST:
                    break
            self.assert_(msg[0] == DIALBACK_REQUEST)
            self.check_drequest(msg[1:])
            
            # Proper behaviour is to try to send a reply using a new return connection
            s2 = BTConnection('localhost',self.hisport,mylistenport=self.mylistenport[i],user_infohash=dialback_infohash)
            s2.read_handshake_medium_rare(close_ok = True)
            if gen_dreply is not None:
                resp = gen_dreply(i)
                print >> sys.stderr,"test: sending DIALBACK_REPLY #",i
                s2.send(resp)
            time.sleep(2)
            # the other side should always close the 
            # connection, either because we're done or he didn't like our
            # bad DIALBACK_REPLY message
            msg = s2.recv()
            if len(msg) > 0:
                print >> sys.stderr,"test: Received unexpected data",getMessageName(msg[0])
            self.assert_(len(msg)==0)
            s2.close()

            # Not really necessary, but helps with test_dialback_active2
            s.close()


        ext_ip = self.session.get_external_ip()
        print >>sys.stderr,"test: External IP address after test is",ext_ip
        
        if diff_ips_test:
            if self.config.sessconfig['dialback_trust_superpeers'] == 1:
                good = True
            else:
                good = False
                
        if good:
            self.assert_(ext_ip == REPLY_IP)
        else:
            self.assert_(ext_ip == self.myoriginalip)

    def create_good_dreply(self,i):
        s = REPLY_IP
        b = bencode(s)
        return DIALBACK_REPLY+b

    def create_not_bdecodable(self,i):
        return DIALBACK_REPLY+"bla"

    def create_not_string(self,i):
        s = 481
        b = bencode(s)
        return DIALBACK_REPLY+b

    def create_not_validip(self,i):
        s = '127..0.0.1'
        b = bencode(s)
        return DIALBACK_REPLY+b

    def create_diff_ips(self,i):
        if self.NLISTENERS==1:
            s = REPLY_IP
        else:
            s = '127.0.0.'+str(i)
        b = bencode(s)
        return DIALBACK_REPLY+b

    def check_drequest(self,data):
        self.assert_(len(data)==0)


def test_suite():
    suite = unittest.TestSuite()
    # We should run the tests in a separate Python interpreter to prevent 
    # problems with our singleton classes, e.g. SuperPeerDB, etc.
    if len(sys.argv) != 2:
        print "Usage: python test_dra.py <method name>"
    else:
        suite.addTest(TestDialbackReplyActive(sys.argv[1]))
    
    return suite

def main():
    unittest.main(defaultTest='test_suite',argv=[sys.argv[0]])
    
if __name__ == "__main__":
    main()
