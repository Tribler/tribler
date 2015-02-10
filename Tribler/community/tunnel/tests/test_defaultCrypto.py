import logging.config
import os
import random
from mock import Mock
import time
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.tunnel import exitstrategies
from Tribler.community.tunnel.tunnel_community import ProxyCommunity, ProxySettings
from Tribler.community.tunnel.crypto.tunnelcrypto import NoCrypto, DefaultCrypto
from Tribler.community.tunnel.payload import CreateMessage, ExtendMessage, CreatedMessage
from Tribler.community.tunnel.routing import Circuit, Hop
from Tribler.dispersy.candidate import WalkCandidate, CANDIDATE_ELIGIBLE_DELAY
from Tribler.dispersy.endpoint import NullEndpoint

from twisted.internet.threads import blockingCallFromThread

logging.config.fileConfig(
    os.path.dirname(os.path.realpath(__file__)) + "/../logger.conf")

__author__ = 'rutger'


class DummyEndpoint(NullEndpoint):

    def send_simple(self, *args):
        pass


class DummyCandidate():

    def __init__(self, key=None):
        # super(DummyCandidate, self).__init__(self)
        self.sock_addr = Mock()
        self.member = Mock()
        if not key:
            key = self.dispersy.crypto.generate_key(u"NID_secp160k1")
        self.member._ec = key

    def get_member(self):
        return self.member


class TestDefaultCrypto(TestAsServer):

    @property
    def crypto(self):
        return self.community.settings.crypto

    @call_on_reactor_thread
    def setUp(self):
        super(TestDefaultCrypto, self).setUp()
        self.__candidate_counter = 0
        self.dispersy = self.session.lm.dispersy

        dispersy = self.dispersy

        keypair = dispersy.crypto.generate_key(u"NID_secp160k1")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

        settings = ProxySettings()
        settings.crypto = DefaultCrypto()

        self.community = dispersy.define_auto_load(ProxyCommunity, dispersy_member, (settings, None), load=True)[0]
        exitstrategies.DefaultExitStrategy(self.session.lm.rawserver, self.community)

        ''' :type : ProxyCommunity '''

    def setUpPreSession(self):
        super(TestDefaultCrypto, self).setUpPreSession()
        self.config.set_dispersy(True)

    @call_on_reactor_thread
    def __create_walk_candidate(self):
        self.__candidate_counter += 1
        wan_address = ("8.8.8.{0}".format(self.__candidate_counter), self.__candidate_counter)
        lan_address = ("0.0.0.0", 0)
        candidate = WalkCandidate(wan_address, False, lan_address, wan_address, u'unknown')

        key = self.dispersy.crypto.generate_key(u"NID_secp160k1")
        member = self.dispersy.get_member(public_key=self.dispersy.crypto.key_to_bin(key.pub()))
        candidate.associate(member)

        now = time.time()
        candidate.walk(now - CANDIDATE_ELIGIBLE_DELAY)
        candidate.walk_response(now)
        return candidate

    def __prepare_for_create(self):
        self.crypto.key_to_forward = '0' * 16

    def __prepare_for_created(self, candidate, circuit_id):
        dh_key = self.crypto._generate_diffie_secret()
        hop = Hop(self.community.my_member._ec.pub())
        hop.dh_secret = dh_key[0]
        hop.dh_first_part = dh_key[1]
        self.community.circuits[circuit_id] = Circuit(circuit_id, 1, candidate, self.community)
        self.community.circuits[circuit_id].unverified_hop = hop
        self.crypto._received_secrets[(candidate.sock_addr, circuit_id)] = dh_key[1]

    def __generate_candidate_list(self):
        list = {}
        list['a'] = 'A'
        list['b'] = 'B'
        return list

    def __add_circuit(self, circuit_id):
        self.crypto.proxy.circuits[circuit_id] = Circuit(circuit_id)

    def __add_relay(self, relay_key=None):
        if not relay_key:
            circuit_id = random.randint(1000)
            relay_key = (Mock(), circuit_id)
        self.crypto.session_keys[relay_key] = "1"

    def test_on_break_relay_existing_key(self):
        relay_key = ("a", "b")
        self.crypto.session_keys[relay_key] = "test"
        self.crypto.on_break_relay(relay_key)
        self.assertNotIn(relay_key, self.crypto.session_keys)

    def test_on_break_relay_non_existing_key(self):
        relay_key = ("a", "b")
        self.assertNotIn(relay_key, self.crypto.session_keys)

    def test_on_break_relay_different_keys(self):
        relay_key = ("a", "b")
        second_relay_key = ("b", "a")
        self.crypto.session_keys[relay_key] = "test"
        self.crypto.on_break_relay(second_relay_key)
        self.assertIn(relay_key, self.crypto.session_keys)
        self.assertNotIn(second_relay_key, self.crypto.session_keys)

    def test__encrypt_decrypt_create_content(self):
        # test own circuit create
        candidate = DummyCandidate(self.community.my_member._ec)

        create_message = CreateMessage()
        circuit_id = 123
        self.community.circuits[123] = Circuit(123, 1, candidate, self.community)
        hop = Hop(self.community.my_member._ec.pub())
        self.community.circuits[123].unverified_hop = hop

        encrypted_create_message = \
            self.crypto._encrypt_create_content(candidate, circuit_id, create_message)

        unverified_hop = self.community.circuits[123].unverified_hop
        unencrypted_key = unverified_hop.dh_first_part
        unencrypted_pub_key = self.community.crypto.key_to_bin(self.community.my_member._ec.pub())
        self.assertNotEquals(unencrypted_key, encrypted_create_message.key)

        decrypted_create_message = self.crypto._decrypt_create_content(candidate, circuit_id, encrypted_create_message)

        self.assertEquals(unencrypted_key, decrypted_create_message.key)
        self.assertEquals(unencrypted_pub_key, decrypted_create_message.public_key)

        # test other circuit create
        self.__prepare_for_create()
        del self.community.circuits[123]
        candidate = DummyCandidate(self.community.my_member._ec)

        create_message = CreateMessage()
        circuit_id = 123
        self.community.circuits[123] = Circuit(123, 1, candidate, self.community)
        hop = Hop(self.community.my_member._ec.pub())
        self.community.circuits[123].unverified_hop = hop

        encrypted_create_message = \
            self.crypto._encrypt_create_content(candidate, circuit_id, create_message)

        unverified_hop = self.community.circuits[123].unverified_hop
        unencrypted_key = unverified_hop.dh_first_part
        unencrypted_pub_key = self.community.crypto.key_to_bin(self.community.my_member._ec.pub())
        self.assertNotEquals(unencrypted_key, encrypted_create_message.key)

        decrypted_create_message = self.crypto._decrypt_create_content(candidate, circuit_id, encrypted_create_message)

        self.assertEquals(unencrypted_key, decrypted_create_message.key)
        self.assertEquals(unencrypted_pub_key, decrypted_create_message.public_key)

    def test__encrypt_decrypt_extend_content(self):
        candidate = DummyCandidate(self.community.my_member._ec)

        extend_message = ExtendMessage(self.community.my_member.mid)
        circuit_id = 123
        self.community.circuits[123] = Circuit(123, 1, candidate, self.community)
        hop = Hop(self.community.my_member._ec.pub())
        self.community.circuits[123].unverified_hop = hop

        encrypted_extend_message = \
            self.crypto._encrypt_extend_content(candidate, circuit_id, extend_message)

        unverified_hop = self.community.circuits[123].unverified_hop
        unencrypted_key = unverified_hop.dh_first_part
        self.assertNotEquals(unencrypted_key, encrypted_extend_message.key)

        decrypted_extend_message = self.crypto._decrypt_create_content(candidate, circuit_id, encrypted_extend_message)

        self.assertEquals(unencrypted_key, decrypted_extend_message.key)
        self.assertEquals(self.community.my_member.mid, decrypted_extend_message.extend_with)

    def test__encrypt_decrypt_created_content(self):
        candidate = DummyCandidate(self.community.my_member._ec)
        candidate_list = self.__generate_candidate_list()

        circuit_id = 123
        self.__prepare_for_created(candidate, circuit_id)

        created_message = CreatedMessage(candidate_list)

        encrypted_created_message = \
            self.crypto._encrypt_created_content(candidate, circuit_id, created_message)

        unverified_hop = self.community.circuits[circuit_id].unverified_hop
        unencrypted_key = unverified_hop.dh_first_part
        self.assertNotEquals(unencrypted_key, encrypted_created_message.key)

        decrypted_created_message = self.crypto._decrypt_created_content(
            candidate, circuit_id, encrypted_created_message)

        self.assertEquals(candidate_list, decrypted_created_message.candidate_list)
