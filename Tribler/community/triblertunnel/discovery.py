from __future__ import absolute_import, division

from random import sample

from ipv8.peerdiscovery.discovery import DiscoveryStrategy


class GoldenRatioStrategy(DiscoveryStrategy):
    """
    Strategy for removing peers once we have too many in the TunnelCommunity.

    This strategy will remove a "normal" peer if the current ratio of "normal" peers to exit node peers is larger
    than the set golden ratio.
    This strategy will remove an exit peer if the current ratio of "normal" peers to exit node peers is smaller than
    the set golden ratio.
    """

    def __init__(self, overlay, golden_ratio=9/16, target_peers=23):
        """
        Initialize the GoldenRatioStrategy.

        :param overlay: the overlay instance to walk over
        :type overlay: TriblerTunnelCommunity
        :param golden_ratio: the ratio of normal/exit node peers to pursue (between 0.0 and 1.0)
        :type golden_ratio: float
        :param target_peers: the amount of peers at which to start removing (>0)
        :type target_peers: int
        :returns: None
        """
        super(GoldenRatioStrategy, self).__init__(overlay)
        self.golden_ratio = golden_ratio
        self.target_peers = target_peers

        assert target_peers > 0
        assert 0.0 <= golden_ratio <= 1.0

    def take_step(self):
        """
        We are asked to update, see if we have enough peers to start culling them.
        If we do have enough peers, select a suitable peer to remove.

        :returns: None
        """
        with self.walk_lock:
            peer_count = len(self.overlay.get_peers())
            if peer_count > self.target_peers:
                exit_count = len(self.overlay.exit_candidates)
                ratio = 1.0 - exit_count/peer_count # Peer count is > 0 per definition
                exit_peers = set(self.overlay.exit_candidates.values())
                if ratio < self.golden_ratio:
                    self.overlay.network.remove_peer(sample(exit_peers, 1)[0])
                elif ratio > self.golden_ratio:
                    self.overlay.network.remove_peer(sample(set(self.overlay.get_peers()) - exit_peers, 1)[0])
