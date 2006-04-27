# Written by Arno Bakker, Jie Yang, Bram Cohen
# see LICENSE.txt for license information

import unittest

import os
import socket
import tempfile
import random
import shutil
import sha
import time
from binascii import b2a_hex
from struct import pack,unpack
from StringIO import StringIO
from threading import Thread,currentThread
from types import DictType, StringType

from test_as_server import TestAsServer
from btconn import BTConnection
from BitTornado.bencode import bencode,bdecode
from BitTornado.BT1.MessageID import CHALLENGE,RESPONSE1,RESPONSE2
from M2Crypto import EC

DEBUG=False

random_size = 1024

class TestPermIDs(TestAsServer):
    """ 
    Testing PermID extension version 1
    """
    
    #def setUp(self):
        # """ inherited from TestAsServer """

    #def tearDown(self):
        # """ inherited from TestAsServer """

    def test_all(self):
        """ 
            I want to start a Tribler client once and then connect to
            it many times. So there must be only one test method
            to prevent setUp() from creating a new client every time.

            The code is constructed so unittest will show the name of the
            (sub)test where the error occured in the traceback it prints.
        """
        # 1. test good challenge/response
        self.subtest_good_challenge_response2()

        # 2. test various bad challenge messages
        self.subtest_bad_chal_not_bdecodable()
        self.subtest_bad_chal_too_short()
        self.subtest_bad_chal_too_big()

        # 3. test various bad response2 messages
        self.subtest_bad_resp2_not_bdecodable()
        self.subtest_bad_resp2_not_dict1()
        self.subtest_bad_resp2_not_dict2()
        self.subtest_bad_resp2_empty_dict()
        self.subtest_bad_resp2_wrong_dict_keys()
        self.subtest_bad_resp2_bad_cert()
        self.subtest_bad_resp2_bad_peerid()
        self.subtest_bad_resp2_bad_sig_input()
        self.subtest_bad_resp2_too_short_randomB()
        self.subtest_bad_resp2_too_short_randomA()
        self.subtest_bad_resp2_wrong_randomB()
        self.subtest_bad_resp2_wrong_randomA()
        self.subtest_bad_resp2_sig_by_other_keypair()

    #
    # Good challenge/reponse
    #
    def subtest_good_challenge_response2(self):
        """ 
            test good challenge and response2 messages
        """
        s = BTConnection('localhost',self.hisport)
        s.read_handshake()
        [rB,chal_data] = self.create_good_challenge()
        s.send(chal_data)
        resp1_data = s.recv()
        self.assert_(resp1_data[0] == RESPONSE1)
        resp1_dict = self.check_response1(resp1_data[1:],rB,s.get_my_id())
        resp2_data = self.create_good_response2(rB,resp1_dict,s.get_his_id())
        s.send(resp2_data)
        time.sleep(10)
        # the other side should not have closed the connection, as
        # this is all valid, so this should not throw an exception:
        s.send('bla')
        s.close()

    def create_good_challenge(self):
        r = "".zfill(random_size)
        return [r,self.create_challenge_payload(r)]

    def create_good_response2(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_list = [rB,resp1_dict['rA'],hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_challenge_payload(self,r):
        return CHALLENGE+bencode(r)

    def create_response2_payload(self,dict):
        return RESPONSE2+bencode(dict)
    
    #
    # Bad challenges
    #    
    def subtest_bad_chal_not_bdecodable(self):
        self._test_bad_challenge(self.create_not_bdecodable_challenge)
    
    def subtest_bad_chal_too_short(self):
        self._test_bad_challenge(self.create_too_short_challenge)

    def subtest_bad_chal_too_big(self):
        self._test_bad_challenge(self.create_too_big_challenge)

    def _test_bad_challenge(self,gen_chal_func):
        s = BTConnection('localhost',self.hisport)
        s.read_handshake()
        [rB,chal_data] = gen_chal_func()
        s.send(chal_data)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assertRaises(Exception, s.recv)
        s.close()

    def create_not_bdecodable_challenge(self):
        r = "".zfill(random_size)
        return [r,CHALLENGE+"hallo"]

    def create_too_short_challenge(self):
        r = "".zfill(random_size-1)  # too short
        return [r,self.create_challenge_payload(r)]

    def create_too_big_challenge(self):
        r = "".zfill(random_size+1)  # too big
        return [r,self.create_challenge_payload(r)]

    #
    # Bad response2
    #    
    def subtest_bad_resp2_not_bdecodable(self):
        self._test_bad_response2(self.create_resp2_not_bdecodable)

    def subtest_bad_resp2_not_dict1(self):
        self._test_bad_response2(self.create_resp2_not_dict1)

    def subtest_bad_resp2_not_dict2(self):
        self._test_bad_response2(self.create_resp2_not_dict2)

    def subtest_bad_resp2_empty_dict(self):
        self._test_bad_response2(self.create_resp2_empty_dict)

    def subtest_bad_resp2_wrong_dict_keys(self):
        self._test_bad_response2(self.create_resp2_wrong_dict_keys)

    def subtest_bad_resp2_bad_cert(self):
        self._test_bad_response2(self.create_resp2_bad_cert)

    def subtest_bad_resp2_bad_peerid(self):
        self._test_bad_response2(self.create_resp2_bad_peerid)

    def subtest_bad_resp2_bad_sig_input(self):
        self._test_bad_response2(self.create_resp2_bad_sig_input)

    def subtest_bad_resp2_too_short_randomB(self):
        self._test_bad_response2(self.create_resp2_too_short_randomB)

    def subtest_bad_resp2_too_short_randomA(self):
        self._test_bad_response2(self.create_resp2_too_short_randomA)

    def subtest_bad_resp2_wrong_randomB(self):
        self._test_bad_response2(self.create_resp2_wrong_randomB)

    def subtest_bad_resp2_wrong_randomA(self):
        self._test_bad_response2(self.create_resp2_wrong_randomA)

    def subtest_bad_resp2_sig_by_other_keypair(self):
        self._test_bad_response2(self.create_resp2_sig_by_other_keypair)

    def _test_bad_response2(self,gen_resp2_func):
        s = BTConnection('localhost',self.hisport)
        s.read_handshake()
        [rB,chal_data] = self.create_good_challenge()
        s.send(chal_data)
        resp1_data = s.recv()
        self.assert_(resp1_data[0] == RESPONSE1)
        resp1_dict = self.check_response1(resp1_data[1:],rB,s.get_my_id())
        resp2_data = gen_resp2_func(rB,resp1_dict,s.get_his_id())
        s.send(resp2_data)
        time.sleep(5)
        # the other side should not like this and close the connection
        self.assertRaises(Exception, s.recv)
        s.close()

    def create_resp2_not_bdecodable(self,rB,resp1_dict,hisid):
        return RESPONSE2+"bla"

    def create_resp2_not_dict1(self,rB,resp1_dict,hisid):
        resp2 = 481
        return self.create_response2_payload(resp2)

    def create_resp2_not_dict2(self,rB,resp1_dict,hisid):
        resp2 = []
        return self.create_response2_payload(resp2)

    def create_resp2_empty_dict(self,rB,resp1_dict,hisid):
        resp2 = {}
        return self.create_response2_payload(resp2)

    def create_resp2_wrong_dict_keys(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['bla1'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        resp2['bla2'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        return self.create_response2_payload(resp2)

    def create_resp2_bad_cert(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        resp2['A'] = hisid
        sig_list = [rB,resp1_dict['rA'],hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_resp2_bad_peerid(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = '\x00\x00\x00\x00\x00\x30\x00\x00'
        sig_list = [rB,resp1_dict['rA'],hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_resp2_bad_sig_input(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_data = '\x00\x00\x00\x00\x00\x30\x00\x00'
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_resp2_too_short_randomB(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_list = ['\x00\x00\x00\x00\x00\x30\x00\x00',resp1_dict['rA'],hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_resp2_too_short_randomA(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_list = [rB,'\x00\x00\x00\x00\x00\x30\x00\x00',hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_resp2_wrong_randomB(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_list = ["wrong".zfill(random_size),resp1_dict['rA'],hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    def create_resp2_wrong_randomA(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_list = [rB,"wrong".zfill(random_size),hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.my_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)


    def create_resp2_sig_by_other_keypair(self,rB,resp1_dict,hisid):
        resp2 = {}
        resp2['certB'] = str(self.my_keypair.pub().get_der())
        resp2['A'] = hisid
        sig_list = [rB,resp1_dict['rA'],hisid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        sig_asn1 = str(self.his_keypair.sign_dsa_asn1(sig_hash))
        resp2['SB'] = sig_asn1
        return self.create_response2_payload(resp2)

    #
    # Utils
    #
    def check_response1(self,resp1_data,rB,myid):
        resp1 = bdecode(resp1_data)
        self.assert_(type(resp1) == DictType)
        self.assert_(resp1.has_key('certA'))
        self.assert_(resp1.has_key('rA'))
        self.assert_(resp1.has_key('B'))
        self.assert_(resp1.has_key('SA'))
        # show throw exception when key no good
        pubA = EC.pub_key_from_der(resp1['certA'])
        rA = resp1['rA']
        self.assert_(type(rA) == StringType)
        self.assert_(len(rA) == random_size)
        B = resp1['B']
        self.assert_(type(B) == StringType)
        self.assert_(B,myid)
        SA = resp1['SA']
        self.assert_(type(SA) == StringType)
        # verify signature
        sig_list = [rA,rB,myid]
        sig_data = bencode(sig_list)
        sig_hash = sha.sha(sig_data).digest()
        self.assert_(pubA.verify_dsa_asn1(sig_hash,SA))
        # Cannot resign the data with his keypair to double check. Signing
        # appears to yield different, supposedly valid sigs each time.
        return resp1


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPermIDs))
    
    return suite

if __name__ == "__main__":
    unittest.main()
