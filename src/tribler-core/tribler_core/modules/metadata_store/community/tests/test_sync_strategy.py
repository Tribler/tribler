from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer

import pytest

from tribler_core.modules.metadata_store.community.sync_strategy import SyncChannels


class MockCommunity(object):
    def __init__(self):
        self.fetch_next_called = False
        self.send_random_to_called = []
        self.get_peers_return = []

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
