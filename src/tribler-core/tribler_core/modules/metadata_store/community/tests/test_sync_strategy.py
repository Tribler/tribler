from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import Network
from ipv8.test.base import TestBase

import pytest

from tribler_core.modules.metadata_store.community.sync_strategy import RemovePeers, SyncChannels


class MockCommunity(object):
    def __init__(self):
        self.fetch_next_called = False
        self.send_random_to_called = []
        self.get_peers_return = []
        self.network = Network()

    def send_random_to(self, peer):
        self.send_random_to_called.append(peer)

    def fetch_next(self):
        self.fetch_next_called = True

    def get_peers(self):
        return self.get_peers_return


@pytest.fixture
def mock_community():
    return MockCommunity()


@pytest.fixture
def strategy(mock_community):
    return SyncChannels(mock_community)


def test_strategy_no_peers(mock_community, strategy):
    """
    If we have no peers, no random entries should have been sent.
    """
    strategy.take_step()
    assert mock_community.send_random_to_called == []


def test_strategy_one_peer(mock_community, strategy):
    """
    If we have one peer, we should send it our channel views and inspect our download queue.
    """
    mock_community.get_peers_return = [Peer(default_eccrypto.generate_key(u"very-low"))]
    strategy.take_step()

    assert len(mock_community.send_random_to_called) == 1
    assert mock_community.get_peers_return[0] == mock_community.send_random_to_called[0]


def test_strategy_multi_peer(mock_community, strategy):
    """
    If we have multiple peers, we should select one and send it our channel views.
    Also, we should still inspect our download queue.
    """
    mock_community.get_peers_return = [
        Peer(default_eccrypto.generate_key(u"very-low")),
        Peer(default_eccrypto.generate_key(u"very-low")),
        Peer(default_eccrypto.generate_key(u"very-low")),
    ]
    strategy.take_step()

    assert len(mock_community.send_random_to_called) == 1
    assert mock_community.send_random_to_called[0] in mock_community.get_peers_return


class TestRemovePeers(TestBase):
    def setUp(self):
        self.community = MockCommunity()
        self.strategy = RemovePeers(self.community)
        return super().setUp()

    def test_strategy_no_peers(self):
        """
        If we have no peers, nothing should happen.
        """
        self.strategy.take_step()

        self.assertSetEqual(set(), self.community.network.verified_peers)

    def test_strategy_one_peer(self):
        """
        If we have one peer, it should not be removed.
        """
        test_peer = Peer(default_eccrypto.generate_key(u"very-low"))
        self.community.network.add_verified_peer(test_peer)
        self.community.get_peers_return.append(test_peer)

        self.strategy.take_step()

        self.assertSetEqual({test_peer}, self.community.network.verified_peers)

    def test_strategy_multi_peer(self):
        """
        If we have over 20 peers, one should be removed.
        """
        for _ in range(21):
            test_peer = Peer(default_eccrypto.generate_key(u"very-low"))
            self.community.network.add_verified_peer(test_peer)
            self.community.get_peers_return.append(test_peer)

        self.strategy.take_step()

        self.assertEqual(20, len(self.community.network.verified_peers))
