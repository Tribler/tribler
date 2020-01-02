from asyncio import Future
from binascii import unhexlify

from tribler_core.modules.dht_health_manager import DHTHealthManager
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest
from tribler_core.tests.tools.tools import timeout
from tribler_core.utilities.unicode import hexlify


class TestDHTHealthManager(TriblerCoreTest):
    """
    This class contains various tests for the DHT health manager.
    """

    async def setUp(self):
        await super(TestDHTHealthManager, self).setUp()

        self.mock_lt_session = MockObject()
        self.mock_lt_session.dht_get_peers = lambda _: None

        self.dht_health_manager = DHTHealthManager(self.mock_lt_session)

    async def tearDown(self):
        await self.dht_health_manager.shutdown_task_manager()
        await super(TestDHTHealthManager, self).tearDown()

    @timeout(10)
    async def test_get_health(self):
        """
        Test fetching the health of a trackerless torrent.
        """
        response = await self.dht_health_manager.get_health(b'a' * 20, timeout=0.1)
        self.assertIsInstance(response, dict)
        self.assertIn('DHT', response)
        self.assertEqual(response['DHT'][0]['infohash'], hexlify(b'a' * 20))

    @timeout(10)
    async def test_existing_get_health(self):
        lookup_future = self.dht_health_manager.get_health(b'a' * 20, timeout=0.1)
        self.assertEqual(self.dht_health_manager.get_health(b'a' * 20, timeout=0.1), lookup_future)
        await lookup_future

    @timeout(10)
    async def test_combine_bloom_filters(self):
        """
        Test combining two bloom filters
        """
        bf1 = bytearray(b'a' * 256)
        bf2 = bytearray(b'a' * 256)
        self.assertEqual(self.dht_health_manager.combine_bloomfilters(bf1, bf2), bf1)

        bf1 = bytearray(b'\0' * 256)
        bf2 = bytearray(b'b' * 256)
        self.assertEqual(self.dht_health_manager.combine_bloomfilters(bf1, bf2), bf2)

    @timeout(10)
    async def test_get_size_from_bloom_filter(self):
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
        self.assertEqual(self.dht_health_manager.get_size_from_bloomfilter(bf), 1224)

        # Maximum capacity
        bf = bytearray(b'\xff' * 256)
        self.assertEqual(self.dht_health_manager.get_size_from_bloomfilter(bf), 6000)

    @timeout(10)
    async def test_receive_bloomfilters(self):
        """
        Test whether the right operations happen when receiving a bloom filter
        """
        infohash = 'a' * 20
        self.dht_health_manager.received_bloomfilters(infohash)  # It should not do anything
        self.assertFalse(self.dht_health_manager.bf_seeders)
        self.assertFalse(self.dht_health_manager.bf_peers)

        self.dht_health_manager.lookup_futures[infohash] = Future()
        self.dht_health_manager.bf_seeders[infohash] = bytearray(256)
        self.dht_health_manager.bf_peers[infohash] = bytearray(256)
        self.dht_health_manager.received_bloomfilters(b'b' * 20,
                                                      bf_seeds=bytearray(b'\xee' * 256),
                                                      bf_peers=bytearray(b'\xff' * 256))
        self.assertEqual(self.dht_health_manager.bf_seeders[infohash], bytearray(b'\xee' * 256))
        self.assertEqual(self.dht_health_manager.bf_peers[infohash], bytearray(b'\xff' * 256))
