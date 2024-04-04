from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

from ipv8.community import Community, CommunitySettings
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from ipv8.test.base import TestBase

from tribler.core.tunnel.discovery import GoldenRatioStrategy

if TYPE_CHECKING:
    from ipv8.peer import Peer


class MockTriblerTunnelCommunity(Community):
    """
    A mocked TriblerTunnelCommunity.
    """

    settings_class = CommunitySettings
    community_id = b"\x00" * 20

    def __init__(self, settings: CommunitySettings) -> None:
        """
        Create a new MockTriblerTunnelCommunity.
        """
        super().__init__(settings)
        self.exit_candidates = []
        self.candidates = {}
        self.send_introduction_request = Mock()

    def get_candidates(self, flag: int) -> list:
        """
        Get exit candidates.
        """
        return self.exit_candidates if flag == PEER_FLAG_EXIT_BT else []

    def get_peers(self) -> set[Peer]:
        """
        Get all known peers.
        """
        return self.network.verified_peers


class TestGoldenRatioStrategy(TestBase[MockTriblerTunnelCommunity]):
    """
    Tests for the GoldenRatioStrategy class.
    """

    def setUp(self) -> None:
        """
        Create two peers.
        """
        self.initialize(MockTriblerTunnelCommunity, 3)
        self.overlay(0).exit_candidates.append(self.peer(2))

    def test_invariant(self) -> None:
        """
        If we are not at our target peer count, don't do anything.
        """
        strategy = GoldenRatioStrategy(self.overlay(0), 0.0, 3)
        strategy.take_step()
        strategy.golden_ratio = 1.0
        strategy.take_step()

        self.assertEqual(2, len(self.network(0).verified_peers))
        self.assertIn(self.peer(1), self.network(0).verified_peers)
        self.assertIn(self.peer(2), self.network(0).verified_peers)

    def test_remove_normal(self) -> None:
        """
        If we have a normal node and an exit node, check if enforcing a ratio of 0.0 removes the normal node.
        """
        strategy = GoldenRatioStrategy(self.overlay(0), 0.0, 1)
        strategy.take_step()

        # The normal peer should be removed
        self.assertEqual(1, len(self.network(0).verified_peers))
        self.assertIn(self.peer(2), self.network(0).verified_peers)

    def test_remove_exit(self) -> None:
        """
        If we have a normal node and an exit node, check if enforcing a ratio of 1.0 removes the exit node.
        """
        strategy = GoldenRatioStrategy(self.overlay(0), 1.0, 1)
        strategy.take_step()

        # The normal peer should be removed
        self.assertEqual(1, len(self.network(0).verified_peers))
        self.assertIn(self.peer(1), self.network(0).verified_peers)

    def test_send_introduction_request(self) -> None:
        """
        If a node has sent us its peer_flag, check if an introduction_request is sent.
        """
        self.overlay(0).candidates[self.peer(2)] = []

        strategy = GoldenRatioStrategy(self.overlay(0), 1.0, 1)
        strategy.take_step()

        self.overlay(0).send_introduction_request.assert_called_once_with(self.peer(1))
