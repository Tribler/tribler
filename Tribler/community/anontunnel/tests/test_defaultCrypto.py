from collections import defaultdict
import random
from threading import Event
from unittest import TestCase
from mock import Mock
import time
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.community.anontunnel import exitstrategies
from Tribler.community.anontunnel.community import ProxyCommunity
from Tribler.community.anontunnel.payload import CreateMessage
from Tribler.community.anontunnel.tests.test_proxyCommunity import \
    DummyEndpoint
from Tribler.dispersy.candidate import WalkCandidate
from Tribler.dispersy.member import Member

__author__ = 'rutger'

class TestDefaultCrypto(TestCase):
    @classmethod
    def setUpClass(cls):
        config = SessionStartupConfig()
        config.set_torrent_checking(False)
        config.set_multicast_local_peer_discovery(False)
        config.set_megacache(False)
        config.set_dispersy(True)
        config.set_swift_proc(False)
        config.set_mainline_dht(False)
        config.set_torrent_collecting(False)
        config.set_libtorrent(False)
        config.set_dht_torrent_collecting(False)
        cls.session_config = config
        cls.session = Session(scfg=cls.session_config)
        cls.session.start()
        while not cls.session.lm.initComplete:
            time.sleep(1)
        cls.dispersy = cls.session.lm.dispersy
        cls.dispersy._endpoint = DummyEndpoint()
        ''' :type : Tribler.dispersy.Dispersy '''

        cls.__candidate_counter = 0

    def setUp(self):
        dispersy = self.dispersy

        def load_community():
            keypair = dispersy.crypto.generate_key(u"NID_secp160k1")
            dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

            proxy_community = dispersy.define_auto_load(ProxyCommunity, (dispersy_member, None, None), load=True)[0]
            ''' :type : ProxyCommunity '''
            exitstrategies.DefaultExitStrategy(self.session.lm.rawserver, proxy_community)

            return proxy_community

        self.community = dispersy.callback.call(load_community)

    def __create_walk_candidate(self):
        candidate = WalkCandidate(("127.0.0.1", self.__candidate_counter), False, ("127.0.0.1", self.__candidate_counter), ("127.0.0.1", self.__candidate_counter), u'unknown')
        key = self.dispersy.crypto.generate_key(u"NID_secp160k1")
        ''' :type : EC '''

        member = []
        def create_member():
            member.append(Member(self.dispersy, key.pub(), self.community.database_id))

        self.dispersy.callback.call(create_member)

        candidate.associate(member[0])
        self.__candidate_counter += 1
        candidate.walk(time.time())
        return candidate

    def __prepare_for_create(self):
        self.crypto.key_to_forward = '0' * 16

    def __add_circuit(self, circuit_id):
        self.crypto.proxy.circuits[circuit_id] = Mock()

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