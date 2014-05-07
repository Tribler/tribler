import logging.config
import os
import random
from mock import Mock
import time
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.anontunnel import exitstrategies
from Tribler.community.anontunnel.community import ProxyCommunity, ProxySettings
from Tribler.community.anontunnel.crypto import NoCrypto, DefaultCrypto
from Tribler.community.anontunnel.payload import CreateMessage
from Tribler.community.anontunnel.routing import Circuit, Hop
from Tribler.community.privatesemantic.conversion import long_to_bytes, bytes_to_long
from Tribler.dispersy.candidate import WalkCandidate, CANDIDATE_ELIGIBLE_DELAY
from Tribler.dispersy.endpoint import NullEndpoint

logging.config.fileConfig(
    os.path.dirname(os.path.realpath(__file__)) + "/../logger.conf")

__author__ = 'rutger'

class DummyEndpoint(NullEndpoint):
    def send_simple(self, *args):
        pass

class DummyCandidate():
    def __init__(self, key=None):
        #super(DummyCandidate, self).__init__(self)
        self.members = []
        self.sock_addr = Mock()
        member = Mock()
        if not key:
            key = self.dispersy.crypto.generate_key(u"NID_secp160k1")
        member._ec = key
        self.members.append(member)

    def get_members(self):
        return self.members


class TestDefaultCrypto(TestAsServer):
    @property
    def crypto(self):
        return self.community.settings.crypto

    def setUp(self):
        super(TestDefaultCrypto, self).setUp()
        self.__candidate_counter = 0
        self.dispersy = self.session.lm.dispersy

        dispersy = self.dispersy

        def load_community():
            keypair = dispersy.crypto.generate_key(u"NID_secp160k1")
            dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

            settings = ProxySettings()
            settings.crypto = DefaultCrypto()

            proxy_community = dispersy.define_auto_load(ProxyCommunity, dispersy_member, (settings, None), load=True)[0]
            exitstrategies.DefaultExitStrategy(self.session.lm.rawserver, proxy_community)

            return proxy_community

        self.community = dispersy.callback.call(load_community)
        ''' :type : ProxyCommunity '''

    def setUpPreSession(self):
        super(TestDefaultCrypto, self).setUpPreSession()
        self.config.set_dispersy(True)

    def __create_walk_candidate(self):
        def __create():
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

        return self.dispersy.callback.call(__create)

    def __prepare_for_create(self):
        self.crypto.key_to_forward = '0' * 16

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

    def test__encrypt_create_content(self):
        #test own circuit create
        candidate = DummyCandidate(self.community.my_member._ec)

        create_message = CreateMessage()
        circuit_id = 123
        self.community.circuits[123] = Circuit(123, 1, candidate, self.community)
        hop = Hop(self.community.my_member._ec.pub())
        self.community.circuits[123].unverified_hop = hop

        encrypted_create_message = \
            self.crypto._encrypt_create_content(candidate, circuit_id, create_message)
        decrypted_create_message = self.crypto._decrypt_create_content(candidate, circuit_id, encrypted_create_message)
        self.assertEquals(create_message, decrypted_create_message)

        #test another circuit create
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
        decrypted_create_message = self.crypto._decrypt_create_content(candidate, circuit_id, encrypted_create_message)
        self.assertEquals(create_message, decrypted_create_message)

    def test__decrypt_create_content(self):
        self.fail()

    def test__encrypt_extend_content(self):
        self.fail()

    def test__decrypt_extend_content(self):
        self.fail()

    def test__encrypt_created_content(self):
        self.fail()

    def test__decrypt_created_content(self):
        self.fail()

    def test__encrypt_extended_content(self):
        self.fail()

    def test__decrypt_extended_content(self):
        self.fail()

    def test__crypto_outgoing_packet(self):
        self.fail()

    def test__crypto_relay_packet(self):
        self.fail()

    def test__crypto_incoming_packet(self):
        self.fail()