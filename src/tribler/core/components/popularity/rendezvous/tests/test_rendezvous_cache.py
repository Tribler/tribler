import time

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase

from tribler.core.components.popularity.rendezvous.rendezvous_cache import RendezvousCache, EMPTY_PEER_CHALLENGE


class TestRendezvousCache(TestBase):
    NUM_NODES = 3

    def setUp(self):
        super().setUp()
        self.peers = [Peer(default_eccrypto.generate_key(u"low")) for _ in range(self.NUM_NODES)]
        self._cache = RendezvousCache()

    def test_add_peer(self):
        self._cache.add_peer(self.peers[0])
        self._cache.add_peer(self.peers[1])
        self.assertEqual(len(self._cache.get_rendezvous_peers()), 2)

    def test_set_rendezvous_challenge(self):
        self._cache.add_peer(self.peers[0])
        self._cache.set_rendezvous_challenge(self.peers[0], b'1234')
        self.assertEqual(self._cache.get_rendezvous_challenge(self.peers[0]), b'1234')

    def test_clear_inactive_peers(self):
        self._cache.add_peer(self.peers[0])
        self._cache.add_peer(self.peers[1])
        self._cache.add_peer(self.peers[2])
        time.sleep(1)

        self._cache.set_rendezvous_challenge(self.peers[0], b'1234')
        self._cache.clear_inactive_peers(1)

        self.assertEqual(len(self._cache.get_rendezvous_peers()), 1)

    def test_clear_peer_challenge(self):
        self._cache.add_peer(self.peers[0], b'1234')
        self._cache.clear_peer_challenge(self.peers[0])
        assert self._cache.get_rendezvous_challenge(self.peers[0]) == EMPTY_PEER_CHALLENGE
