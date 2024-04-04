from __future__ import annotations

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import Network
from ipv8.test.base import TestBase

from tribler.core.rendezvous.database import RendezvousDatabase
from tribler.core.rendezvous.rendezvous_hook import RendezvousHook


class MockedRendezvousHook(RendezvousHook):
    """
    A mocked RendezvousHook that allows for time to be controlled.
    """

    def __init__(self, rendezvous_db: RendezvousDatabase, mocked_time: float | None = None) -> None:
        """
        Create a new MockedRendezvousHook with a certain time set.
        """
        super().__init__(rendezvous_db)
        self.mocked_time = mocked_time

    @property
    def current_time(self) -> float:
        """
        Fetch the current time.
        """
        if self.mocked_time is None:
            return super().current_time
        return self.mocked_time


class TestRendezvousDatabase(TestBase):
    """
    Tests for the RendezvousHook class.
    """

    def setUp(self) -> None:
        """
        Create a peer and a memory-based database.
        """
        super().setUp()
        self.peer = Peer(default_eccrypto.generate_key("curve25519").pub())
        self.memdb = RendezvousDatabase(":memory:")
        self.hook = MockedRendezvousHook(self.memdb)

    async def tearDown(self) -> None:
        """
        Shut down the database.
        """
        self.memdb.shutdown()
        self.hook.shutdown(Network())
        await super().tearDown()

    def test_peer_added(self) -> None:
        """
        Test if peers are not added to the database after an add hook yet.
        """
        self.hook.on_peer_added(self.peer)

        retrieved = self.memdb.get(self.peer)

        self.assertEqual(0, len(retrieved))

    def test_peer_removed(self) -> None:
        """
        Test if peers are correctly added to the database after a remove hook.
        """
        self.hook.on_peer_added(self.peer)
        self.hook.mocked_time = self.peer.creation_time + 1.0
        self.hook.on_peer_removed(self.peer)

        retrieved = self.memdb.get(self.peer)

        self.assertEqual(1, len(retrieved))
        self.assertEqual((self.peer.creation_time, self.hook.mocked_time), (retrieved[0].start, retrieved[0].stop))

    def test_peer_store_on_shutdown(self) -> None:
        """
        Test if peers are correctly added to the database when shutting down.
        """
        network = Network()
        network.add_verified_peer(self.peer)
        self.hook.on_peer_added(self.peer)
        self.hook.mocked_time = self.peer.creation_time + 1.0
        self.hook.shutdown(network)

        retrieved = self.memdb.get(self.peer)

        self.assertEqual(1, len(retrieved))
        self.assertEqual((self.peer.creation_time, self.hook.mocked_time), (retrieved[0].start, retrieved[0].stop))

    def test_peer_ignore_future(self) -> None:
        """
        Test if peers are not added from the future.
        """
        self.hook.on_peer_added(self.peer)
        self.hook.mocked_time = self.peer.creation_time - 1.0
        self.hook.on_peer_removed(self.peer)

        retrieved = self.memdb.get(self.peer)

        self.assertEqual(0, len(retrieved))
