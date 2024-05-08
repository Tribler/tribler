from __future__ import annotations

import time
from random import choice
from typing import TYPE_CHECKING

from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from ipv8.peerdiscovery.discovery import DiscoveryStrategy

if TYPE_CHECKING:
    from ipv8.types import Peer

    from tribler.core.tunnel.community import TriblerTunnelCommunity


class GoldenRatioStrategy(DiscoveryStrategy):
    """
    Strategy for removing peers once we have too many in the TunnelCommunity.

    This strategy will remove a "normal" peer if the current ratio of "normal" peers to exit node peers is larger
    than the set golden ratio.
    This strategy will remove an exit peer if the current ratio of "normal" peers to exit node peers is smaller than
    the set golden ratio.
    """

    def __init__(self, overlay: TriblerTunnelCommunity, golden_ratio: float = 9 / 16, target_peers: int = 23) -> None:
        """
        Initialize the GoldenRatioStrategy.

        :param overlay: the overlay instance to walk over
        :param golden_ratio: the ratio of normal/exit node peers to pursue (between 0.0 and 1.0)
        :param target_peers: the amount of peers at which to start removing (>0)
        """
        super().__init__(overlay)
        self.golden_ratio = golden_ratio
        self.target_peers = target_peers
        self.intro_sent: dict[Peer, float] = {}

        assert target_peers > 0
        assert 0.0 <= golden_ratio <= 1.0

    def take_step(self) -> None:
        """
        We are asked to update, see if we have enough peers to start culling them.
        If we do have enough peers, select a suitable peer to remove.
        """
        with self.walk_lock:
            peers = self.overlay.get_peers()
            for peer in list(self.intro_sent.keys()):
                if peer not in peers:
                    self.intro_sent.pop(peer, None)

            # Some of the peers in the community could have been discovered using the DiscoveryCommunity. If this
            # happens we have no knowledge of their peer_flags. In order to still get the flags we send them an
            # introduction request manually.
            now = time.time()
            for peer in peers:
                if peer not in self.overlay.candidates and now > self.intro_sent.get(peer, 0) + 300:
                    self.overlay.send_introduction_request(peer)
                    self.intro_sent[peer] = now

            peer_count = len(peers)
            if peer_count > self.target_peers:
                exit_peers = set(self.overlay.get_candidates(PEER_FLAG_EXIT_BT))
                exit_count = len(exit_peers)
                ratio = 1.0 - exit_count / peer_count  # Peer count is > 0 per definition
                if ratio < self.golden_ratio:
                    self.overlay.network.remove_peer(choice(list(exit_peers)))
                elif ratio > self.golden_ratio:
                    self.overlay.network.remove_peer(choice(list(set(self.overlay.get_peers()) - exit_peers)))
