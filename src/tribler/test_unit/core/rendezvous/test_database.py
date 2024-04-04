from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase

from tribler.core.rendezvous.database import RendezvousDatabase


class TestRendezvousDatabase(TestBase):
    """
    Tests for the RendezvousDatabase class.
    """

    def setUp(self) -> None:
        """
        Create a peer and a memory-based database.
        """
        super().setUp()
        self.peer = Peer(default_eccrypto.generate_key("curve25519").pub())
        self.memdb = RendezvousDatabase(":memory:")

    async def tearDown(self) -> None:
        """
        Shut down the database.
        """
        self.memdb.shutdown()
        await super().tearDown()

    def test_retrieve_no_certificates(self) -> None:
        """
        Test if we start out without certificates.
        """
        retrieved = self.memdb.get(self.peer)

        self.assertEqual(0, len(retrieved))

    def test_retrieve_single_certificate(self) -> None:
        """
        Test if we can add a single certificate.
        """
        start_timestamp, stop_timestamp = range(1, 3)
        self.memdb.add(self.peer, start_timestamp, stop_timestamp)

        retrieved = self.memdb.get(self.peer)

        self.assertEqual(1, len(retrieved))
        self.assertEqual((start_timestamp, stop_timestamp), (retrieved[0].start, retrieved[0].stop))

    def test_retrieve_multiple_certificates(self) -> None:
        """
        Test if we can add multiple certificates.
        """
        start_timestamp1, stop_timestamp1, start_timestamp2, stop_timestamp2 = range(1, 5)
        self.memdb.add(self.peer, start_timestamp1, stop_timestamp1)
        self.memdb.add(self.peer, start_timestamp2, stop_timestamp2)

        retrieved = self.memdb.get(self.peer)

        self.assertEqual(2, len(retrieved))
        self.assertEqual((start_timestamp1, stop_timestamp1), (retrieved[0].start, retrieved[0].stop))
        self.assertEqual((start_timestamp2, stop_timestamp2), (retrieved[1].start, retrieved[1].stop))

    def test_retrieve_filter_certificates(self) -> None:
        """
        Test if we can retrieve certificates with a filter.
        """
        peer2 = Peer(default_eccrypto.generate_key("curve25519").pub())
        start_timestamp1, stop_timestamp1, start_timestamp2, stop_timestamp2 = range(1, 5)
        self.memdb.add(self.peer, start_timestamp1, stop_timestamp1)
        self.memdb.add(peer2, start_timestamp2, stop_timestamp2)

        retrieved = self.memdb.get(self.peer)

        self.assertEqual(1, len(retrieved))
        self.assertEqual((start_timestamp1, stop_timestamp1), (retrieved[0].start, retrieved[0].stop))
