from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import Network

from tribler_core.components.tunnel.community.discovery import GoldenRatioStrategy


class FakeOverlay:

    def __init__(self):
        self.exit_candidates = []
        self.candidates = {}
        self.network = Network()
        self.send_introduction_request = Mock()

    def get_candidates(self, flag):
        return self.exit_candidates if flag == PEER_FLAG_EXIT_BT else []

    def get_peers(self):
        return self.network.verified_peers


def generate_peer():
    return Peer(default_eccrypto.generate_key("very-low"))


def generate_overlay_and_peers():
    overlay = FakeOverlay()
    peer1 = generate_peer()  # Normal peer
    peer2 = generate_peer()  # Exit node
    overlay.exit_candidates.append(peer2)
    overlay.network.add_verified_peer(peer1)
    overlay.network.add_verified_peer(peer2)
    return overlay, peer1, peer2


def test_invariant():
    """
    If we are not at our target peer count, don't do anything.
    """
    overlay, peer1, peer2 = generate_overlay_and_peers()

    # Apply the strategy, we are not at 3 peers, so nothing should happen
    strategy = GoldenRatioStrategy(overlay, 0.0, 3)
    strategy.take_step()
    strategy.golden_ratio = 1.0
    strategy.take_step()

    # Nobody should be removed
    assert len(overlay.network.verified_peers) == 2
    assert peer1 in overlay.network.verified_peers
    assert peer2 in overlay.network.verified_peers


def test_remove_normal():
    """
    If we have a normal node and an exit node, check if enforcing a ratio of 0.0 removes the normal node.
    """
    overlay, _, peer2 = generate_overlay_and_peers()

    # Apply the strategy of 0 normal nodes for each exit node
    strategy = GoldenRatioStrategy(overlay, 0.0, 1)
    strategy.take_step()

    # The normal peer should be removed
    assert len(overlay.network.verified_peers) == 1
    assert peer2 in overlay.network.verified_peers


def test_remove_exit():
    """
    If we have a normal node and an exit node, check if enforcing a ratio of 1.0 removes the exit node.
    """
    overlay, peer1, _ = generate_overlay_and_peers()

    # Apply the strategy of 1 normal nodes for each exit node
    strategy = GoldenRatioStrategy(overlay, 1.0, 1)
    strategy.take_step()

    # The normal peer should be removed
    assert len(overlay.network.verified_peers) == 1
    assert peer1 in overlay.network.verified_peers


def test_send_introduction_request():
    """
    If a node has sent us its peer_flag, check if an introduction_request is sent.
    """
    overlay, peer1, peer2 = generate_overlay_and_peers()
    overlay.candidates[peer2] = []

    strategy = GoldenRatioStrategy(overlay, 1.0, 1)
    strategy.take_step()

    overlay.send_introduction_request.assert_called_once_with(peer1)
