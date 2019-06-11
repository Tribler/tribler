from __future__ import absolute_import

from unittest import TestCase

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import Network

from Tribler.community.triblertunnel.discovery import GoldenRatioStrategy
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_ANY


class FakeOverlay(object):

    def __init__(self):
        self.exit_candidates = []
        self.network = Network()

    def get_candidates(self, flag):
        return self.exit_candidates if flag == PEER_FLAG_EXIT_ANY else []

    def get_peers(self):
        return self.network.verified_peers


class TestGoldenRatio(TestCase):

    @staticmethod
    def _generate_peer():
        return Peer(default_eccrypto.generate_key(u"very-low"))

    @classmethod
    def _generate_overlay_and_peers(cls):
        overlay = FakeOverlay()
        peer1 = cls._generate_peer()  # Normal peer
        peer2 = cls._generate_peer()  # Exit node
        overlay.exit_candidates.append(peer2)
        overlay.network.add_verified_peer(peer1)
        overlay.network.add_verified_peer(peer2)
        return overlay, peer1, peer2

    def test_invariant(self):
        """
        If we are not at our target peer count, don't do anything.
        """
        overlay, peer1, peer2 = self._generate_overlay_and_peers()

        # Apply the strategy, we are not at 3 peers, so nothing should happen
        strategy = GoldenRatioStrategy(overlay, 0.0, 3)
        strategy.take_step()
        strategy.golden_ratio = 1.0
        strategy.take_step()

        # Nobody should be removed
        self.assertEqual(2, len(overlay.network.verified_peers))
        self.assertIn(peer1, overlay.network.verified_peers)
        self.assertIn(peer2, overlay.network.verified_peers)

    def test_remove_normal(self):
        """
        If we have a normal node and an exit node, check if enforcing a ratio of 0.0 removes the normal node.
        """
        overlay, _, peer2 = self._generate_overlay_and_peers()

        # Apply the strategy of 0 normal nodes for each exit node
        strategy = GoldenRatioStrategy(overlay, 0.0, 1)
        strategy.take_step()

        # The normal peer should be removed
        self.assertEqual(1, len(overlay.network.verified_peers))
        self.assertIn(peer2, overlay.network.verified_peers)

    def test_remove_exit(self):
        """
        If we have a normal node and an exit node, check if enforcing a ratio of 1.0 removes the exit node.
        """
        overlay, peer1, _ = self._generate_overlay_and_peers()

        # Apply the strategy of 1 normal nodes for each exit node
        strategy = GoldenRatioStrategy(overlay, 1.0, 1)
        strategy.take_step()

        # The normal peer should be removed
        self.assertEqual(1, len(overlay.network.verified_peers))
        self.assertIn(peer1, overlay.network.verified_peers)
