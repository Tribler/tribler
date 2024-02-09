from __future__ import annotations

from typing import Generator

import pytest

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from tribler.core.components.ipv8.rendezvous.db.database import RendezvousDatabase
from tribler.core.components.ipv8.settings import RendezvousSettings
from tribler.core.utilities.utilities import MEMORY_DB


class MockedRendezvousDB(RendezvousDatabase):

    def __init__(self, db_type: str, decay_coefficient: float, decay_granularity: float, stale_timeout: float,
                 mocked_time: float | None = None) -> None:
        super().__init__(db_type, decay_coefficient, decay_granularity, stale_timeout)
        self.mocked_time = mocked_time

    @property
    def current_time(self) -> float:
        if self.mocked_time is None:
            return super().current_time
        return self.mocked_time


@pytest.fixture(name="memdb", scope="function")
def fixture_memory_database() -> Generator[RendezvousDatabase, None, None]:
    default_config = RendezvousSettings()
    db = MockedRendezvousDB(MEMORY_DB, default_config.decay_coefficient, default_config.decay_granularity,
                            default_config.stale_timeout)

    yield db

    db.shutdown()


def generate_peer() -> Peer:
    public_key = default_eccrypto.generate_key("curve25519").pub()
    return Peer(public_key)


@pytest.fixture(name="peer", scope="module")
def fixture_peer() -> Generator[Peer, None, None]:
    yield generate_peer()


@pytest.fixture(name="peer2", scope="function")
def fixture_peer2() -> Generator[Peer, None, None]:
    yield generate_peer()


def test_retrieve_no_peer_score(peer: Peer, memdb: RendezvousDatabase) -> None:
    retrieved = memdb.get(peer)

    assert retrieved is None


def test_retrieve_single_certificate(peer: Peer, memdb: RendezvousDatabase) -> None:
    start_timestamp, stop_timestamp = (1, 3)
    memdb.mocked_time = stop_timestamp
    memdb.add(peer, start_timestamp, stop_timestamp)
    retrieved = memdb.get(peer)

    assert retrieved is not None
    assert retrieved.public_key == peer.public_key.key_to_bin()
    assert retrieved.total == 2.0
    assert retrieved.count == 1
    assert retrieved.last_updated == stop_timestamp


def test_retrieve_multiple_certificates(peer: Peer, memdb: RendezvousDatabase) -> None:
    start_timestamp1, stop_timestamp1, start_timestamp2, stop_timestamp2 = range(1, 5)
    memdb.mocked_time = stop_timestamp1
    memdb.add(peer, start_timestamp1, stop_timestamp1)
    memdb.mocked_time = stop_timestamp2
    memdb.add(peer, start_timestamp2, stop_timestamp2)

    retrieved = memdb.get(peer)

    assert retrieved is not None
    assert retrieved.public_key == peer.public_key.key_to_bin()
    assert 1.99 < retrieved.total < 2.0  # Slightly less than 2.0 due to decay
    assert retrieved.count == 2
    assert retrieved.last_updated == stop_timestamp2


def test_decay(peer: Peer, peer2: Peer, memdb: RendezvousDatabase) -> None:
    memdb.mocked_time = 2
    memdb.add(peer, 1, 2)
    memdb.add(peer2, 1, 2)

    memdb.mocked_time = 5
    memdb.add(peer, 4, 5)

    memdb.mocked_time = 7
    memdb.add(peer, 6, 7)
    memdb.add(peer2, 5, 7)

    retrieved1 = memdb.get(peer)
    retrieved2 = memdb.get(peer2)

    assert retrieved1 is not None and retrieved2 is not None
    print(retrieved1.total / 3, retrieved2.total / 2)
    assert retrieved1.total < retrieved2.total
