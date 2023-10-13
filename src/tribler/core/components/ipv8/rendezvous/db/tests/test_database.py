from typing import Generator

import pytest

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from tribler.core.components.ipv8.rendezvous.db.database import RendezvousDatabase
from tribler.core.utilities.utilities import MEMORY_DB


@pytest.fixture(name="memdb", scope="function")
def fixture_memory_database() -> Generator[RendezvousDatabase, None, None]:
    db = RendezvousDatabase(MEMORY_DB)

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


def test_retrieve_no_certificates(peer: Peer, memdb: RendezvousDatabase) -> None:
    retrieved = memdb.get(peer)

    assert len(retrieved) == 0


def test_retrieve_single_certificate(peer: Peer, memdb: RendezvousDatabase) -> None:
    start_timestamp, stop_timestamp = range(1, 3)
    memdb.add(peer, start_timestamp, stop_timestamp)

    retrieved = memdb.get(peer)

    assert len(retrieved) == 1
    assert retrieved[0].start, retrieved[0].stop == (start_timestamp, stop_timestamp)


def test_retrieve_multiple_certificates(peer: Peer, memdb: RendezvousDatabase) -> None:
    start_timestamp1, stop_timestamp1, start_timestamp2, stop_timestamp2 = range(1, 5)
    memdb.add(peer, start_timestamp1, stop_timestamp1)
    memdb.add(peer, start_timestamp2, stop_timestamp2)

    retrieved = memdb.get(peer)

    assert len(retrieved) == 2
    assert retrieved[0].start, retrieved[0].stop == (start_timestamp1, stop_timestamp1)
    assert retrieved[1].start, retrieved[1].stop == (start_timestamp2, stop_timestamp2)


def test_retrieve_filter_certificates(peer: Peer, peer2: Peer, memdb: RendezvousDatabase) -> None:
    start_timestamp1, stop_timestamp1, start_timestamp2, stop_timestamp2 = range(1, 5)
    memdb.add(peer, start_timestamp1, stop_timestamp1)
    memdb.add(peer2, start_timestamp2, stop_timestamp2)

    retrieved = memdb.get(peer)

    assert len(retrieved) == 1
    assert retrieved[0].start, retrieved[0].stop == (start_timestamp1, stop_timestamp1)
