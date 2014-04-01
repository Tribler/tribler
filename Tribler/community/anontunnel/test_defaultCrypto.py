from collections import defaultdict
import random
from threading import Event
from unittest import TestCase
from mock import Mock
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.cache import CandidateCache
from Tribler.community.anontunnel.community import ProxyCommunity
from Tribler.community.anontunnel.crypto import DefaultCrypto
from Tribler.community.anontunnel.endpoint import DispersyBypassEndpoint
from Tribler.community.anontunnel.payload import CreateMessage
from Tribler.community.privatesemantic.crypto.elgamalcrypto import ElgamalCrypto
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.candidate import WalkCandidate
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.member import Member

__author__ = 'rutger'

class TestDefaultCrypto(TestCase):

    def setUp(self):
        raw_server = RawServer(Event(), 10, 100)
        self.dispersy = Dispersy(Callback(), DispersyBypassEndpoint(raw_server,0), u".", u":memory:", ElgamalCrypto())
        self.dispersy.start()
        self.crypto = DefaultCrypto()

        obj = Mock()
        obj.crypto = ElgamalCrypto()
        obj.callback = Callback()

        self.cache = CandidateCache(obj)
        self.__candidate_counter = 0

        def load_community():
            keypair = self.dispersy.crypto.generate_key(u"NID_secp160k1")
            dispersy_member = self.dispersy.callback.call(self.dispersy.get_member,
                (self.dispersy.crypto.key_to_bin(keypair.pub()),
                 self.dispersy.crypto.key_to_bin(keypair)))

            self.proxy = self.dispersy.define_auto_load(
                    ProxyCommunity, (dispersy_member, None, None), load=True)[0]
        self.dispersy.callback.call(load_community)
        self.crypto.set_proxy(self.proxy)


    def __prepare_for_create(self):
        self.crypto.key_to_forward = '0' * 16

    def __add_circuit(self, circuit_id):
        self.crypto.proxy.circuits[circuit_id] = Mock()

    def __add_relay(self, relay_key=None):
        if not relay_key:
            circuit_id = random.randint(1000)
            relay_key = (Mock(), circuit_id)
        self.crypto.session_keys[relay_key] = "1"

    def __create_walk_candidate(self):
        candidate = WalkCandidate(("127.0.0.1", self.__candidate_counter), False, ("127.0.0.1", self.__candidate_counter), ("127.0.0.1", self.__candidate_counter), u'unknown')
        key = self.dispersy.crypto.generate_key(u"NID_secp160k1")
        ''' :type : EC '''

        member = []
        def create_member():
            member.append(Member(self.dispersy, self.dispersy.crypto.key_to_bin(key.pub())))

        self.dispersy.callback.call(create_member)

        candidate.associate(member[0])
        self.__candidate_counter += 1
        return candidate

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
        create_message = CreateMessage("a")
        self.__prepare_for_create()
        candidate = self.__create_walk_candidate()
        circuit_id = 123
        encrypted_create_message = \
            self.crypto._encrypt_create_content(candidate, circuit_id, create_message)
        decrypted_create_message = self.crypto._decrypt_create_content(candidate, circuit_id, encrypted_create_message)
        self.assertEquals(encrypted_create_message, decrypted_create_message)

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