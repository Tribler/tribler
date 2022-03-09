from unittest.mock import Mock

from ipv8.util import succeed

import pytest

from tribler_core.components.payout.payout_manager import PayoutManager


@pytest.fixture
async def payout_manager():
    fake_bw_community = Mock()

    fake_response_peer = Mock()
    fake_response_peer.public_key = Mock()
    fake_response_peer.public_key.key_to_bin = lambda: b'a' * 64
    fake_dht = Mock()
    fake_dht.connect_peer = lambda *_: succeed([fake_response_peer])

    payout_manager = PayoutManager(fake_bw_community, fake_dht)
    yield payout_manager
    await payout_manager.shutdown()


@pytest.mark.asyncio
async def test_do_payout(payout_manager):
    """
    Test doing a payout
    """
    res = await payout_manager.do_payout(b'a')  # Does not exist
    assert not res
    payout_manager.update_peer(b'b', b'c', 10 * 1024 * 1024)
    payout_manager.update_peer(b'b', b'd', 1337)

    def mocked_do_payout(*_, **__):
        return succeed(None)

    payout_manager.bandwidth_community.do_payout = mocked_do_payout
    res = await payout_manager.do_payout(b'b')
    assert res


@pytest.mark.asyncio
async def test_do_payout_dht_error(payout_manager):
    """
    Test whether we are not doing a payout when the DHT lookup fails
    """
    def err_connect_peer(_):
        raise RuntimeError("test")

    payout_manager.update_peer(b'a', b'b', 10 * 1024 * 1024)
    payout_manager.dht.connect_peer = err_connect_peer
    res = await payout_manager.do_payout(b'a')
    assert not res


@pytest.mark.asyncio
async def test_do_payout_no_dht_peers(payout_manager):
    """
    Test whether we are not doing a payout when there are no peers returned by the DHT
    """
    def connect_peer(_):
        return succeed([])

    payout_manager.update_peer(b'a', b'b', 10 * 1024 * 1024)
    payout_manager.dht.connect_peer = connect_peer
    res = await payout_manager.do_payout(b'a')
    assert not res


@pytest.mark.asyncio
async def test_do_payout_error(payout_manager):
    """
    Test whether we are not doing a payout when the payout fails
    """
    def connect_peer(_):
        return succeed([b"abc"])

    def do_payout(*_):
        raise RuntimeError("test")

    payout_manager.update_peer(b'a', b'b', 10 * 1024 * 1024)
    payout_manager.dht.connect_peer = connect_peer
    payout_manager.bandwidth_community.do_payout = do_payout
    res = await payout_manager.do_payout(b'a')
    assert not res


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
