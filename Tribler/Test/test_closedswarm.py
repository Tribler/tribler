# Written by Njaal Borch
# see LICENSE.txt for license information
#
import time
from base64 import encodestring,decodestring

import unittest

import os.path
from Tribler.Core.Overlay import permid
from Tribler.Core.MessageID import *

from Tribler.Core.ClosedSwarm import ClosedSwarm

class ClosedSwarmTest(unittest.TestCase):

    def setUp(self):
        self.keyfiles = [".node_a_keypair",".node_b_keypair",".torrent_keypair"]
        for filename in self.keyfiles:
            if not os.path.exists(filename):
                keypair = permid.generate_keypair()
                permid.save_keypair(keypair, filename)
                
        self.node_a_keypair = permid.read_keypair(".node_a_keypair")
        self.node_b_keypair = permid.read_keypair(".node_b_keypair")
        self.torrent_keypair = permid.read_keypair(".torrent_keypair")

        self.torrent_id = "1234"

        # Shortcuts
        self.node_a_pub_permid = str(self.node_a_keypair.pub().get_der())
        self.node_b_pub_permid = str(self.node_b_keypair.pub().get_der())
        self.torrent_pubkeys = [encodestring(str(self.torrent_keypair.pub().get_der())).replace("\n","")]
        
        # Create the certificate for this torrent ("proof of access")
        self.poa_a = ClosedSwarm.create_poa(self.torrent_id,
                                            self.torrent_keypair,
                                            self.node_a_pub_permid)

        self.poa_b = ClosedSwarm.create_poa(self.torrent_id,
                                            self.torrent_keypair,
                                            self.node_b_pub_permid)
        
        self.cs_a = ClosedSwarm.ClosedSwarm(self.node_a_keypair,
                                            self.torrent_id,
                                            self.torrent_pubkeys,
                                            self.poa_a)
        
        self.cs_b = ClosedSwarm.ClosedSwarm(self.node_b_keypair,
                                            self.torrent_id,
                                            self.torrent_pubkeys,
                                            self.poa_b)


    def tearDown(self):
        for filename in self.keyfiles:
            try:
                os.remove(filename)
            except:
                pass

    def _verify_poas(self, poa_a, poa_b):
        self.assertEquals(poa_a.torrent_id, poa_b.torrent_id)
        self.assertEquals(poa_a.torrent_pub_key, poa_b.torrent_pub_key)
        self.assertEquals(poa_a.node_pub_key, poa_b.node_pub_key)
        self.assertEquals(poa_a.signature, poa_b.signature)
        self.assertEquals(poa_a.expire_time, poa_b.expire_time)
        
    def test_poa_serialization(self):


        serialized = self.poa_a.serialize()
        deserialized = ClosedSwarm.POA.deserialize(serialized)
        self._verify_poas(self.poa_a, deserialized)
        deserialized.verify()

        self.poa_a.save("poa.tmp")
        new_poa = ClosedSwarm.POA.load("poa.tmp")
        new_poa.verify()
        
        # Also serialize/deserialize using lists
        serialized = self.poa_a.serialize_to_list()
        deserialized = self.poa_a.deserialize_from_list(serialized)
        self._verify_poas(self.poa_a, deserialized)
        deserialized.verify()
        
        
    def test_poa(self):
        self.poa_a.verify()
        self.poa_b.verify()


        # Test poa expiretime
        expire_time = time.mktime(time.gmtime())+60 # Expire in one minute
        
        self.poa_a = ClosedSwarm.create_poa(self.torrent_id,
                                            self.torrent_keypair,
                                            self.node_a_pub_permid,
                                            expire_time=expire_time)
        try:
            self.poa_a.verify()
        except ClosedSwarm.POAExpiredException:
            self.fail("POA verify means expired, but it is not")

        expire_time = time.mktime(time.gmtime())-1 # Expire one second ago
        
        self.poa_a = ClosedSwarm.create_poa(self.torrent_id,
                                            self.torrent_keypair,
                                            self.node_a_pub_permid,
                                            expire_time=expire_time)
        try:
            self.poa_a.verify()
            self.fail("POA verify does not honor expire time")
        except ClosedSwarm.POAExpiredException:
            pass


    def test_basic(self):
        self.assertFalse(self.cs_a.remote_node_authorized)
        self.assertFalse(self.cs_b.remote_node_authorized)

    def test_node_a_valid(self):
        """
        Test that the protocol works if only node A wants to be authorized
        """
        msg_1 = self.cs_a.a_create_challenge()
        msg_2 = self.cs_b.b_create_challenge(msg_1)
        msg_3 = self.cs_a.a_provide_poa_message(msg_2)
        msg_4 = self.cs_b.b_provide_poa_message(msg_3, i_am_seeding=True)
        if msg_4:
            self.fail("Made POA message for node B even though it is seeding")

        self.assertFalse(self.cs_a.is_remote_node_authorized())
        self.assertTrue(self.cs_b.is_remote_node_authorized())


    def test_poa_message_creation(self):
        
        msg_1 = self.cs_a.a_create_challenge()
        msg_2 = self.cs_b.b_create_challenge(msg_1)

        
        msg = self.cs_a._create_poa_message(CS_POA_EXCHANGE_A, self.cs_a.my_nonce, self.cs_b.my_nonce)
        try:
            self.cs_a._validate_poa_message(msg, self.cs_a.my_nonce, self.cs_b.my_nonce)
        except Exception,e:
            self.fail("_create_poa_message and _validate_poa_message do not agree: %s"%e)


    def test_both_valid(self):
        """
        Test that the protocol works if both nodes wants to be authorized
        """
        msg_1 = self.cs_a.a_create_challenge()
        nonce_a = self.cs_a.my_nonce
        
        msg_2 = self.cs_b.b_create_challenge(msg_1)
        nonce_b = self.cs_b.my_nonce

        msg_3 = self.cs_a.a_provide_poa_message(msg_2)

        self.assertEquals(self.cs_a.remote_nonce, nonce_b, "A's remote nonce is wrong")
            
        msg_4 = self.cs_b.b_provide_poa_message(msg_3)
        self.assertEquals(self.cs_b.remote_nonce, nonce_a, "B's remote nonce is wrong")

        self.assertEquals(self.cs_a.my_nonce, self.cs_b.remote_nonce, "B's remote nonce is not A's nonce")
        self.assertEquals(self.cs_a.remote_nonce, self.cs_b.my_nonce, "A's remote nonce is not B's nonce")

        self.cs_a.a_check_poa_message(msg_4)
        
        
        self.assertTrue(self.cs_a.is_remote_node_authorized())
        self.assertTrue(self.cs_b.is_remote_node_authorized())

        
    def test_not_fresh_node_a(self):

        msg_1 = self.cs_a.a_create_challenge()
        bad_msg_1 = [CS_CHALLENGE_A,
                     self.torrent_id,
                     "badchallenge_a"]
        msg_2 = self.cs_b.b_create_challenge(bad_msg_1)
        msg_3 = self.cs_a.a_provide_poa_message(msg_2)
        msg_4 = self.cs_b.b_provide_poa_message(msg_3)
        try:
            self.cs_a.a_check_poa_message(msg_4)
            self.fail("Did not discover bad signature")
        except ClosedSwarm.InvalidSignatureException,e:
            pass

        # Nobody can succeed now, the challenges are bad
        self.assertFalse(self.cs_a.is_remote_node_authorized())
        self.assertFalse(self.cs_b.is_remote_node_authorized())
        

    def test_not_fresh_node_b(self):

        msg_1 = self.cs_a.a_create_challenge()
        msg_2 = self.cs_b.b_create_challenge(msg_1)
        bad_msg_2 = [CS_CHALLENGE_B,
                     self.torrent_id,
                     "badchallenge_b"]
        msg_3 = self.cs_a.a_provide_poa_message(bad_msg_2)
        msg_4 = self.cs_b.b_provide_poa_message(msg_3)
        try:
            self.cs_a.a_check_poa_message(msg_4)
            self.fail("Failed to discover bad POA from B")
        except:
            pass

        # Nobody can succeed now, the challenges are bad
        self.assertFalse(self.cs_a.is_remote_node_authorized())
        self.assertFalse(self.cs_b.is_remote_node_authorized())


    def test_invalid_poa_node_a(self):

        self.cs_a.poa = ClosedSwarm.POA("bad_poa_a", "stuff", "stuff2")

        # Update to a bad POA
        msg_1 = self.cs_a.a_create_challenge()
        msg_2 = self.cs_b.b_create_challenge(msg_1)
        msg_3 = self.cs_a.a_provide_poa_message(msg_2)
        msg_4 = self.cs_b.b_provide_poa_message(msg_3)
        self.cs_a.a_check_poa_message(msg_4)
        
        self.assertTrue(self.cs_a.is_remote_node_authorized())
        self.assertFalse(self.cs_b.is_remote_node_authorized())
        

    def test_very_invalid_poa_node_a(self):

        # Update to a bad POA
        try:
            self.cs_a.set_poa("Wrong class!")
            self.fail("Allows a string as POA!")
        except:
            pass

    def test_invalid_swarm_node_b(self):

        # Update to a bad POA
        self.cs_b.poa = ClosedSwarm.POA("bad_poa_b", "stuff", "stuff2")

        # Update to a bad POA
        msg_1 = self.cs_a.a_create_challenge()
        msg_2 = self.cs_b.b_create_challenge(msg_1)
        msg_3 = self.cs_a.a_provide_poa_message(msg_2)
        msg_4 = self.cs_b.b_provide_poa_message(msg_3)
        try:
            self.cs_a.a_check_poa_message(msg_4)
            self.fail("Node B failed to discover bad POA")
        except ClosedSwarm.WrongSwarmException,e:
            pass

    def test_invalid_poa_node_b(self):
        self.cs_b.poa = ClosedSwarm.POA(self.torrent_id, "stuff", "stuff2")

        # Update to a bad POA
        msg_1 = self.cs_a.a_create_challenge()
        msg_2 = self.cs_b.b_create_challenge(msg_1)
        msg_3 = self.cs_a.a_provide_poa_message(msg_2)
        msg_4 = self.cs_b.b_provide_poa_message(msg_3)
        try:
            self.cs_a.a_check_poa_message(msg_4)
            self.fail("Node B failed to discover bad POA")
        except ClosedSwarm.InvalidPOAException,e:
            pass

    
if __name__ == "__main__":

    print "Performing ClosedSwarm unit tests"


    unittest.main()

    print "All done"

