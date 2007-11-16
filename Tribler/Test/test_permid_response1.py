# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

# This test checks how the Tribler code responds to bad RESPONSE1 messages.
# To test this we would have to have Tribler connect to us, that is,
# initiate the challenge response. As it is not trivial to let the client 
# connect to another (us) we have written a different solution:
#
# 1. We create our own server listening to a given TCP port. 
# 2. We create a bogus Encrypter/Connecter Connection object encapsulating a 
#    normal TCP connection to our server.
# 3. We pass the bogus Connection object to the permid.ChallengeResponse class 
#    and tell it to initiate the C/R protocol.
# 4. Our server responds with malformed RESPONSE1 messages.
#
import unittest

import sys
import socket
import tempfile
import sha
import shutil
import time
from threading import Thread,currentThread
from types import DictType, StringType
from traceback import print_exc

from btconn import BTConnection
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.BT1.MessageID import CHALLENGE,RESPONSE1,RESPONSE2
import Tribler.Core.Overlay.permid as permid
from M2Crypto import EC

DEBUG=False

#
# CAUTION: when a test is added to MyServer.test_all(), increase test_count and 
# make sure the should_succeed flag to TestPermIDsResponse1.subtest_connect()
# is set correctly.
#
test_count = 13

random_size = 1024  # the number of random bytes in the C/R protocol

class MyServer(Thread):
    
    def __init__(self,port,testcase):
        Thread.__init__(self)
        self.testcase = testcase
        self.port = port
        self.my_keypair = EC.gen_params(EC.NID_sect233k1)
        self.my_keypair.gen_key()

        self.other_keypair = EC.gen_params(EC.NID_sect233k1)
        self.other_keypair.gen_key()


    def run(self):
        try:
            self.runReal()
        except Exception,e:
            print_exc()
            self.testcase.assert_(False,str(e))

    def runReal(self):
        ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ss.bind(('', self.port))
        ss.listen(1)
        self.test_all(ss)
        ss.close()
        print "myserver: Server thread ending"

    def test_all(self,ss):
        """
            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        #
        # CAUTION: when a test is added here, increase test_count and make
        # sure the should_succeed flag to TestPermIDsResponse1.subtest_connect()
        # is set correctly.
        ## Good must be first
        self.subtest_good_response1(ss)
        self.subtest_bad_resp1_no_bdecoable(ss)
        self.subtest_bad_resp1_not_dict1(ss)
        self.subtest_bad_resp1_not_dict2(ss)
        self.subtest_bad_resp1_empty_dict(ss)
        self.subtest_bad_resp1_wrong_dict_keys(ss)
        self.subtest_bad_resp1_bad_cert(ss)
        self.subtest_bad_resp1_too_short_randomA(ss)
        self.subtest_bad_resp1_bad_peerid(ss)
        self.subtest_bad_resp1_bad_sig_input(ss)
        self.subtest_bad_resp1_too_short_randomB(ss)
        self.subtest_bad_resp1_wrong_randomB(ss)
        self.subtest_bad_resp1_sig_by_other_key(ss)

    def subtest_good_response1(self,ss):
            self._test_response1(ss, self.create_good_response1,True)

    def subtest_bad_resp1_no_bdecoable(self,ss):
            self._test_response1(ss, self.create_bad_resp1_no_bdecodable,False)
    
    def subtest_bad_resp1_not_dict1(self,ss):
            self._test_response1(ss, self.create_bad_resp1_not_dict1,False)

    def subtest_bad_resp1_not_dict2(self,ss):
            self._test_response1(ss, self.create_bad_resp1_not_dict2,False)

    def subtest_bad_resp1_empty_dict(self,ss):
            self._test_response1(ss, self.create_bad_resp1_empty_dict,False)

    def subtest_bad_resp1_wrong_dict_keys(self,ss):
            self._test_response1(ss, self.create_bad_resp1_wrong_dict_keys,False)

    def subtest_bad_resp1_bad_cert(self,ss):
            self._test_response1(ss, self.create_bad_resp1_bad_cert,False)

    def subtest_bad_resp1_too_short_randomA(self,ss):
            self._test_response1(ss, self.create_bad_resp1_too_short_randomA,False)

    def subtest_bad_resp1_bad_peerid(self,ss):
            self._test_response1(ss, self.create_bad_resp1_bad_peerid,False)

    def subtest_bad_resp1_bad_sig_input(self,ss):
            self._test_response1(ss, self.create_bad_resp1_bad_sig_input,False)

    def subtest_bad_resp1_too_short_randomB(self,ss):
            self._test_response1(ss, self.create_bad_resp1_too_short_randomB,False)

    def subtest_bad_resp1_wrong_randomB(self,ss):
            self._test_response1(ss, self.create_bad_resp1_bad_randomB,False)

    def subtest_bad_resp1_sig_by_other_key(self,ss):
            self._test_response1(ss, self.create_bad_resp1_sig_by_other_key,False)

    def _test_response1(self,ss,gen_resp1,good):
        print >>sys.stderr,"test: myserver running:",gen_resp1
        conn, addr = ss.accept()
        s = BTConnection('',0,conn)
        s.read_handshake_medium_rare()
        # Read challenge
        msg = s.recv()
        self.testcase.assert_(msg[0] == CHALLENGE)
        randomB = bdecode(msg[1:])
        self.testcase.assert_(type(randomB) == StringType)
        self.testcase.assert_(len(randomB) == random_size)
        [randomA,resp1_data] = gen_resp1(randomB,s.get_his_id())
        s.send(resp1_data)
        if good:
            # Read response2
            msg = s.recv()
            self.testcase.assert_(msg[0] == RESPONSE2)
            self.check_response2(msg[1:],randomA,randomB,s.get_my_id())
            # the connection should be intact, so this should not throw an
            # exception:
            time.sleep(5)
            s.send('bla')
            s.close()
        else:
            time.sleep(5)
            # the other side should not our bad RESPONSE1 this and close the 
            # connection
            msg = s.recv()
            self.testcase.assert_(len(msg)==0)
            s.close()


    def create_good_response1(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = "".zfill(random_size)
        resp1['B'] = hisid
        sig_list = [resp1['rA'],rB,hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

    def create_response1_payload(self,dict):
        return RESPONSE1+bencode(dict)

    def check_response2(self,resp2_data,rA,rB,myid):
        resp2 = bdecode(resp2_data)
        self.testcase.assert_(type(resp2) == DictType)
        self.testcase.assert_(resp2.has_key('certB'))
        self.testcase.assert_(resp2.has_key('A'))
        self.testcase.assert_(resp2.has_key('SB'))
        # show throw exception when key no good
        pubB = EC.pub_key_from_der(resp2['certB'])
        A = resp2['A']
        self.testcase.assert_(type(A) == StringType)
        self.testcase.assert_(A,myid)
        SB = resp2['SB']
        self.testcase.assert_(type(SB) == StringType)
        # verify signature
        sig_list = [rB,rA,myid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        self.testcase.assert_(pubB.verify_dsa_asn1(sig_hash,SB))
        # Cannot resign the data with his keypair to double check. Signing
        # appears to yield different, supposedly valid sigs each time.

    def create_bad_resp1_no_bdecodable(self,rB,hisid):
        r = "".zfill(random_size)
        return [r,RESPONSE1+'bla']

    def create_bad_resp1_not_dict1(self,rB,hisid):
        resp1 = 481
        r = "".zfill(random_size)
        return [r,self.create_response1_payload(resp1)]

    def create_bad_resp1_not_dict2(self,rB,hisid):
        resp1 = []
        r = "".zfill(random_size)
        return [r,self.create_response1_payload(resp1)]

    def create_bad_resp1_empty_dict(self,rB,hisid):
        resp1 = {}
        r = "".zfill(random_size)
        return [r,self.create_response1_payload(resp1)]

    def create_bad_resp1_wrong_dict_keys(self,rB,hisid):
        resp1 = {}
        resp1['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        resp1['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        r = "".zfill(random_size)
        return [r,self.create_response1_payload(resp1)]

    def create_bad_resp1_bad_cert(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        resp1['rA'] = "".zfill(random_size)
        resp1['B'] = hisid
        sig_list = [resp1['rA'],rB,hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

    def create_bad_resp1_too_short_randomA(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        resp1['B'] = hisid
        sig_list = [resp1['rA'],rB,hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

    def create_bad_resp1_bad_peerid(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = "".zfill(random_size)
        resp1['B'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        sig_list = [resp1['rA'],rB,hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

    def create_bad_resp1_bad_sig_input(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = "".zfill(random_size)
        resp1['B'] = hisid
        sig_list = [resp1['rA'],rB,hisid]
        sig_data = '\x00\x00\x00\x00\x00\x30\x00\x00'
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

    def create_bad_resp1_too_short_randomB(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = "".zfill(random_size)
        resp1['B'] = hisid
        sig_list = [resp1['rA'],'\x00\x00\x00\x00\x00\x30\x00\x00',hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

    def create_bad_resp1_bad_randomB(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = "".zfill(random_size)
        resp1['B'] = hisid
        sig_list = [resp1['rA'],"wrong".zfill(random_size),hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]


    def create_bad_resp1_sig_by_other_key(self,rB,hisid):
        resp1 = {}
        resp1['certA'] = str(self.my_keypair.pub().get_der())
        resp1['rA'] = "".zfill(random_size)
        resp1['B'] = hisid
        sig_list = [resp1['rA'],rB,hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.other_keypair.sign_dsa_asn1(sig_hash))
        resp1['SA'] = sig_asn1
        return [resp1['rA'],self.create_response1_payload(resp1)]

#
# Proxy class to fool the ChallengeReponse class
#

class EncrypterConnection:
    def __init__(self,myid):
        self.id = myid

class ConnecterConnection:

    def __init__(self,port):
        self.s = BTConnection('localhost',port)
        self.s.read_handshake_medium_rare()
        self.connection = EncrypterConnection(self.s.get_his_id())

    def get_my_id(self):
        return self.s.get_my_id()

    def get_unauth_peer_id(self):
        return self.s.get_his_id()

    def is_locally_initiated(self):
        return True

    def send_message(self,msg):
        self.s.send(msg)
        
    def get_message(self):
        return self.s.recv()

    def set_permid(self,x):
        pass

    def set_auth_peer_id(self,x):
        pass

    def close(self):
        self.s.close()

class SecureOverlay:
    def __init__(self):
        pass

    def got_auth_connection(self,singsock,permid,peer_id):
        pass

#
# The actual TestCase
#
class TestPermIDsResponse1(unittest.TestCase):
    """ 
    Testing PermID extension version 1, RESPONSE1 message.
    """
    
    def setUp(self):
        self.config_path = tempfile.mkdtemp()
        permid.init(self.config_path)

        self.server_port = 4810
        self.server = MyServer(self.server_port,self)
        self.server.start()
        time.sleep(1) # allow server to start

        self.overlay = SecureOverlay()

    def tearDown(self):
        shutil.rmtree(self.config_path)

    def test_all(self):
        """ 
            I want to start my test server once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new server every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        for count in range(test_count):
            if count == 0:
                self.subtest_connect(True) # first test is good response1
            else:
                self.subtest_connect(False) # others are bad

    def subtest_connect(self,should_succeed):
        if DEBUG:
            print "client: subtest_connect"
        self.conn = ConnecterConnection(self.server_port)
        self.myid = self.conn.get_my_id()

        self.cr = permid.ChallengeResponse(permid.get_my_keypair(),self.myid,self.overlay)
        self.cr.start_cr(self.conn)
        resp1_data = self.conn.get_message()
        success = self.cr.got_message(self.conn,resp1_data)
        if success and should_succeed:
            # Correct behaviour is to keep connection open.
            # long enough for MyServer to test if the connection still exists
            time.sleep(10) 
            self.conn.close()
        elif not success and not should_succeed:
            # Correct behaviour is to close conn immediately.
            self.conn.close()
        elif success and not should_succeed:
            # Correct behaviour is to keep connection open.
            # Should have failed
            self.assert_(False,"Tribler should not have accepted RESPONSE1")
            time.sleep(10)  # Emulate we're still running
            self.conn.close()
        elif not success and should_succeed:
            # Correct behaviour is to close conn immediately.
            # Should have succeeded
            self.assert_(False,"Tribler should have accepted RESPONSE1")
            self.conn.close()

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPermIDsResponse1))
    
    return suite

if __name__ == "__main__":
    unittest.main()
