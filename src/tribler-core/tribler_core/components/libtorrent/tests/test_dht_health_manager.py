from asyncio import Future
from binascii import unhexlify

from asynctest import Mock

import pytest

from tribler_core.components.libtorrent.download_manager.dht_health_manager import DHTHealthManager
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
async def dht_health_manager():
    manager = DHTHealthManager(lt_session=Mock())
    yield manager
    await manager.shutdown_task_manager()


@pytest.mark.asyncio
async def test_get_health(dht_health_manager):
    """
    Test fetching the health of a trackerless torrent.
    """
    response = await dht_health_manager.get_health(b'a' * 20, timeout=0.1)
    assert isinstance(response, dict)
    assert 'DHT' in response
    assert response['DHT'][0]['infohash'] == hexlify(b'a' * 20)


@pytest.mark.asyncio
async def test_existing_get_health(dht_health_manager):
    lookup_future = dht_health_manager.get_health(b'a' * 20, timeout=0.1)
    assert dht_health_manager.get_health(b'a' * 20, timeout=0.1) == lookup_future
    await lookup_future


@pytest.mark.asyncio
async def test_combine_bloom_filters(dht_health_manager):
    """
    Test combining two bloom filters
    """
    bf1 = bytearray(b'a' * 256)
    bf2 = bytearray(b'a' * 256)
    assert dht_health_manager.combine_bloomfilters(bf1, bf2) == bf1

    bf1 = bytearray(b'\0' * 256)
    bf2 = bytearray(b'b' * 256)
    assert dht_health_manager.combine_bloomfilters(bf1, bf2) == bf2


@pytest.mark.asyncio
async def test_get_size_from_bloom_filter(dht_health_manager):
    """
    Test whether we can successfully estimate the size from a bloom filter
    """
    # See http://www.bittorrent.org/beps/bep_0033.html
    bf = bytearray(unhexlify("""F6C3F5EA A07FFD91 BDE89F77 7F26FB2B FF37BDB8 FB2BBAA2 FD3DDDE7 BACFFF75 EE7CCBAE
                                FE5EEDB1 FBFAFF67 F6ABFF5E 43DDBCA3 FD9B9FFD F4FFD3E9 DFF12D1B DF59DB53 DBE9FA5B
                                7FF3B8FD FCDE1AFB 8BEDD7BE 2F3EE71E BBBFE93B CDEEFE14 8246C2BC 5DBFF7E7 EFDCF24F
                                D8DC7ADF FD8FFFDF DDFFF7A4 BBEEDF5C B95CE81F C7FCFF1F F4FFFFDF E5F7FDCB B7FD79B3
                                FA1FC77B FE07FFF9 05B7B7FF C7FEFEFF E0B8370B B0CD3F5B 7F2BD93F EB4386CF DD6F7FD5
                                BFAF2E9E BFFFFEEC D67ADBF7 C67F17EF D5D75EBA 6FFEBA7F FF47A91E B1BFBB53 E8ABFB57
                                62ABE8FF 237279BF EFBFEEF5 FFC5FEBF DFE5ADFF ADFEE1FB 737FFFFB FD9F6AEF FEEE76B6
                                FD8F72EF""".replace(' ', '').replace('\n', '')))
    assert dht_health_manager.get_size_from_bloomfilter(bf) == 1224

    # Maximum capacity
    bf = bytearray(b'\xff' * 256)
    assert dht_health_manager.get_size_from_bloomfilter(bf) == 6000


@pytest.mark.asyncio
async def test_receive_bloomfilters(dht_health_manager):
    """
    Test whether the right operations happen when receiving a bloom filter
    """
    infohash = b'a' * 20
    transaction_id = '1'
    dht_health_manager.received_bloomfilters(transaction_id)  # It should not do anything
    assert not dht_health_manager.bf_seeders
    assert not dht_health_manager.bf_peers

    dht_health_manager.lookup_futures[infohash] = Future()
    dht_health_manager.bf_seeders[infohash] = bytearray(256)
    dht_health_manager.bf_peers[infohash] = bytearray(256)
    dht_health_manager.requesting_bloomfilters(transaction_id, infohash)
    dht_health_manager.received_bloomfilters(transaction_id,
                                             bf_seeds=bytearray(b'\xee' * 256),
                                             bf_peers=bytearray(b'\xff' * 256))
    assert dht_health_manager.bf_seeders[infohash] == bytearray(b'\xee' * 256)
    assert dht_health_manager.bf_peers[infohash] == bytearray(b'\xff' * 256)
