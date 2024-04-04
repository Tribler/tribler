from asyncio import Future
from binascii import unhexlify
from unittest.mock import Mock

from ipv8.test.base import TestBase

from tribler.core.libtorrent.download_manager.dht_health_manager import DHTHealthManager


class TestDHTHealthManager(TestBase):
    """
    Tests for the DHTHealthManager class.
    """

    bf_contents = unhexlify("F6C3F5EAA07FFD91BDE89F777F26FB2BFF37BDB8FB2BBAA2FD3DDDE7BACFFF75EE7CCBAE"
                            "FE5EEDB1FBFAFF67F6ABFF5E43DDBCA3FD9B9FFDF4FFD3E9DFF12D1BDF59DB53DBE9FA5B"
                            "7FF3B8FDFCDE1AFB8BEDD7BE2F3EE71EBBBFE93BCDEEFE148246C2BC5DBFF7E7EFDCF24F"
                            "D8DC7ADFFD8FFFDFDDFFF7A4BBEEDF5CB95CE81FC7FCFF1FF4FFFFDFE5F7FDCBB7FD79B3"
                            "FA1FC77BFE07FFF905B7B7FFC7FEFEFFE0B8370BB0CD3F5B7F2BD93FEB4386CFDD6F7FD5"
                            "BFAF2E9EBFFFFEECD67ADBF7C67F17EFD5D75EBA6FFEBA7FFF47A91EB1BFBB53E8ABFB57"
                            "62ABE8FF237279BFEFBFEEF5FFC5FEBFDFE5ADFFADFEE1FB737FFFFBFD9F6AEFFEEE76B6"
                            "FD8F72EF")

    def setUp(self) -> None:
        """
        Create a mocked DHTHealthManager.
        """
        super().setUp()
        self.manager = DHTHealthManager(lt_session=Mock())

    async def tearDown(self) -> None:
        """
        Shut down the health manager.
        """
        await self.manager.shutdown_task_manager()
        await super().tearDown()

    async def test_get_health(self) -> None:
        """
        Test if the health of a trackerless torrent can be fetched.
        """
        health = await self.manager.get_health(b"a" * 20, timeout=0.01)

        self.assertEqual(b"a" * 20, health.infohash)

    async def test_existing_get_health(self) -> None:
        """
        Test if the same future is returned for the same query.
        """
        lookup_future = self.manager.get_health(b"a" * 20, timeout=0.01)

        self.assertEqual(lookup_future, self.manager.get_health(b"a" * 20, timeout=0.01))
        await lookup_future

    async def test_combine_bloom_filters_equal(self) -> None:
        """
        Test if two bloom equal filters can be combined.
        """
        bf1 = bytearray(b"a" * 256)
        bf2 = bytearray(b"a" * 256)

        self.assertEqual(bf1, self.manager.combine_bloomfilters(bf1, bf2))

    async def test_combine_bloom_filters_different(self) -> None:
        """
        Test if two bloom different filters can be combined.
        """
        bf1 = bytearray(b"\0" * 256)
        bf2 = bytearray(b"b" * 256)

        self.assertEqual(bf2, self.manager.combine_bloomfilters(bf1, bf2))

    def test_get_size_from_bloom_filter(self) -> None:
        """
        Test if we can successfully estimate the size from a bloom filter.

        See http://www.bittorrent.org/beps/bep_0033.html
        """
        bf = bytearray(TestDHTHealthManager.bf_contents)

        self.assertEqual(1224, self.manager.get_size_from_bloomfilter(bf))

    def test_get_size_from_bloom_filter_maximum(self) -> None:
        """
        Test if we can successfully estimate the size of a bloom filter at maximum capacity.
        """
        bf = bytearray(b"\xff" * 256)

        self.assertEqual(6000, self.manager.get_size_from_bloomfilter(bf))

    def test_receive_bloomfilters_nothing(self) -> None:
        """
        Test if just receiving a transactions id does nothing to the bloom filter.
        """
        self.manager.received_bloomfilters("1")

        self.assertEqual({}, self.manager.bf_seeders)
        self.assertEqual({}, self.manager.bf_peers)

    def test_receive_bloomfilters(self) -> None:
        """
        Test if the right operations happens when receiving a bloom filter.
        """
        infohash = b"a" * 20
        self.manager.lookup_futures[infohash] = Future()
        self.manager.bf_seeders[infohash] = bytearray(256)
        self.manager.bf_peers[infohash] = bytearray(256)
        self.manager.requesting_bloomfilters("1", infohash)

        self.manager.received_bloomfilters("1",
                                           bf_seeds=bytearray(b"\xee" * 256),
                                           bf_peers=bytearray(b"\xff" * 256))

        self.assertEqual(bytearray(b"\xee" * 256), self.manager.bf_seeders[infohash])
        self.assertEqual(bytearray(b"\xff" * 256), self.manager.bf_peers[infohash])
