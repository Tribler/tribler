from unittest.mock import Mock

from ipv8.util import succeed

import pytest

from tribler_core.modules.payout_manager import PayoutManager


@pytest.fixture
def payout_manager():
    fake_bw_community = Mock()

    fake_response_peer = Mock()
    fake_response_peer.public_key = Mock()
    fake_response_peer.public_key.key_to_bin = lambda: b'a' * 64
    fake_dht = Mock()
    fake_dht.connect_peer = lambda *_: succeed([fake_response_peer])

    payout_manager = PayoutManager(fake_bw_community, fake_dht)
    return payout_manager


@pytest.mark.asyncio
async def test_do_payout(payout_manager):
    """
    Test doing a payout
    """
    await payout_manager.do_payout(b'a')  # Does not exist
    payout_manager.update_peer(b'b', b'c', 10 * 1024 * 1024)
    payout_manager.update_peer(b'b', b'd', 1337)

    def mocked_do_payout(*_, **__):
        return succeed(None)

    payout_manager.bandwidth_community.do_payout = mocked_do_payout
    await payout_manager.do_payout(b'b')


def test_update_peer(payout_manager):
    """
    Test the updating of a specific peer
    """
    payout_manager.update_peer(b'a', b'b', 1337)
    assert b'a' in payout_manager.tribler_peers
    assert b'b' in payout_manager.tribler_peers[b'a']
    assert payout_manager.tribler_peers[b'a'][b'b'] == 1337

    payout_manager.update_peer(b'a', b'b', 1338)
    assert payout_manager.tribler_peers[b'a'][b'b'] == 1338
