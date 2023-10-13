from __future__ import annotations

from typing import Generator

import pytest

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.peerdiscovery.network import Network
from tribler.core.components.ipv8.rendezvous.db.database import RendezvousDatabase
from tribler.core.components.ipv8.rendezvous.rendezvous_hook import RendezvousHook
from tribler.core.utilities.utilities import MEMORY_DB


class MockedRendezvousHook(RendezvousHook):

    def __init__(self, rendezvous_db: RendezvousDatabase, mocked_time: float | None = None) -> None:
        super().__init__(rendezvous_db)
        self.mocked_time = mocked_time

    @property
    def current_time(self) -> float:
        if self.mocked_time is None:
            return super().current_time
        return self.mocked_time


@pytest.fixture(name="memdb", scope="function")
def fixture_memory_database() -> Generator[RendezvousDatabase, None, None]:
    db = RendezvousDatabase(MEMORY_DB)

    yield db

    db.shutdown()


@pytest.fixture(name="hook", scope="function")
def fixture_hook(memdb: RendezvousDatabase) -> Generator[MockedRendezvousHook, None, None]:
    hook = MockedRendezvousHook(memdb)

    yield hook

    hook.shutdown(Network())


@pytest.fixture(name="peer", scope="module")
def fixture_peer() -> Generator[Peer, None, None]:
    public_key = default_eccrypto.generate_key("curve25519").pub()
    yield Peer(public_key)


def test_peer_added(peer: Peer, hook: MockedRendezvousHook, memdb: RendezvousDatabase) -> None:
    hook.on_peer_added(peer)

    retrieved = memdb.get(peer)
    assert len(retrieved) == 0


def test_peer_removed(peer: Peer, hook: MockedRendezvousHook, memdb: RendezvousDatabase) -> None:
    hook.on_peer_added(peer)

    hook.mocked_time = peer.creation_time + 1.0
    hook.on_peer_removed(peer)

    retrieved = memdb.get(peer)
    assert len(retrieved) == 1
    assert retrieved[0].start, retrieved[0].stop == (peer.creation_time, hook.mocked_time)


def test_peer_store_on_shutdown(peer: Peer, hook: MockedRendezvousHook, memdb: RendezvousDatabase) -> None:
    network = Network()
    network.add_verified_peer(peer)
    hook.on_peer_added(peer)
    hook.mocked_time = peer.creation_time + 1.0

    hook.shutdown(network)

    retrieved = memdb.get(peer)
    assert len(retrieved) == 1
    assert retrieved[0].start, retrieved[0].stop == (peer.creation_time, hook.mocked_time)


def test_peer_ignore_future(peer: Peer, hook: MockedRendezvousHook, memdb: RendezvousDatabase) -> None:
    hook.on_peer_added(peer)

    hook.mocked_time = peer.creation_time - 1.0
    hook.on_peer_removed(peer)

    retrieved = memdb.get(peer)
    assert len(retrieved) == 0
