from typing import Generator

from pony.orm import db_session
from pytest import fixture

from tribler.core.components.database.db.layers.user_activity_layer import UserActivityLayer
from tribler.core.components.user_activity.types import InfoHash
from tribler.core.utilities.pony_utils import TrackedDatabase


@fixture(name="layer")
def fixture_activity_layer() -> Generator[UserActivityLayer, None, None]:
    database = TrackedDatabase()
    database.bind(provider="sqlite", filename=":memory:")
    ual = UserActivityLayer(database)
    database.generate_mapping(create_tables=True)
    yield ual
    database.disconnect()


def float_equals(a: float, b: float) -> bool:
    return round(a, 5) == round(b, 5)


def test_store_no_losers(layer: UserActivityLayer) -> None:
    """
    Test that queries can be stored and retrieved.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), set())

    with db_session():
        queries = layer.Query.select()[:]

        assert len(queries) == 1
        assert queries[0].query == "test query"
        assert len(queries[0].infohashes) == 1
        assert list(queries[0].infohashes)[0].infohash == b"\x00" * 20
        assert float_equals(list(queries[0].infohashes)[0].preference, 1.0)


def test_store_with_loser(layer: UserActivityLayer) -> None:
    """
    Test that queries with a loser can be stored and retrieved.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

    with db_session():
        queries = layer.Query.select()[:]
        winner, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
        loser, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]

        assert len(queries) == 1
        assert queries[0].query == "test query"
        assert float_equals(winner.preference, 1.0)
        assert float_equals(loser.preference, 0.0)


def test_store_with_losers(layer: UserActivityLayer) -> None:
    """
    Test that queries with multiple losers can be stored and retrieved.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                       InfoHash(b"\x02" * 20),
                                                       InfoHash(b"\x03" * 20)})

    with db_session():
        queries = layer.Query.select()[:]
        winner, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
        loser_1, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
        loser_2, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
        loser_3, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]

        assert len(queries) == 1
        assert queries[0].query == "test query"
        assert float_equals(winner.preference, 1.0)
        assert float_equals(loser_1.preference, 0.0)
        assert float_equals(loser_2.preference, 0.0)
        assert float_equals(loser_3.preference, 0.0)


def test_store_weighted_decay(layer: UserActivityLayer) -> None:
    """
    Test result decay after updating.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                       InfoHash(b"\x02" * 20),
                                                       InfoHash(b"\x03" * 20)})
    layer.store("test query", InfoHash(b"\x01" * 20), {InfoHash(b"\x00" * 20),
                                                       InfoHash(b"\x02" * 20),
                                                       InfoHash(b"\x03" * 20)})

    with db_session():
        queries = layer.Query.select()[:]
        entry_1, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
        entry_2, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
        entry_3, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
        entry_4, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]

        assert len(queries) == 1
        assert queries[0].query == "test query"
        assert float_equals(entry_1.preference, 0.2)
        assert float_equals(entry_2.preference, 0.8)
        assert float_equals(entry_3.preference, 0.0)
        assert float_equals(entry_4.preference, 0.0)


def test_store_delete_old(layer: UserActivityLayer) -> None:
    """
    Test result decay after updating.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                       InfoHash(b"\x02" * 20),
                                                       InfoHash(b"\x03" * 20)})
    layer.store("test query", InfoHash(b"\x04" * 20), {InfoHash(b"\x00" * 20),
                                                       InfoHash(b"\x01" * 20),
                                                       InfoHash(b"\x02" * 20)})

    with db_session():
        queries = layer.Query.select()[:]
        entry_1, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
        entry_2, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
        entry_3, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
        should_be_dropped = layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]
        entry_4, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x04" * 20)[:]

        assert len(queries) == 1
        assert queries[0].query == "test query"
        assert float_equals(entry_1.preference, 0.2)
        assert float_equals(entry_2.preference, 0.0)
        assert float_equals(entry_3.preference, 0.0)
        assert should_be_dropped == []
        assert float_equals(entry_4.preference, 0.8)


def test_store_delete_old_over_e(layer: UserActivityLayer) -> None:
    """
    Test if entries are not deleted if their preference is still over the threshold e.
    """
    layer.e = 0.0
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20),
                                                       InfoHash(b"\x02" * 20),
                                                       InfoHash(b"\x03" * 20)})
    layer.store("test query", InfoHash(b"\x04" * 20), {InfoHash(b"\x00" * 20),
                                                       InfoHash(b"\x01" * 20),
                                                       InfoHash(b"\x02" * 20)})

    with db_session():
        queries = layer.Query.select()[:]
        entry_1, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x00" * 20)[:]
        entry_2, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x01" * 20)[:]
        entry_3, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x02" * 20)[:]
        entry_4, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x03" * 20)[:]
        entry_5, = layer.InfohashPreference.select(lambda x: x.infohash == b"\x04" * 20)[:]

        assert len(queries) == 1
        assert queries[0].query == "test query"
        assert float_equals(entry_1.preference, 0.2)
        assert float_equals(entry_2.preference, 0.0)
        assert float_equals(entry_3.preference, 0.0)
        assert float_equals(entry_4.preference, 0.0)
        assert float_equals(entry_5.preference, 0.8)


def test_get_preferable(layer: UserActivityLayer) -> None:
    """
    Test if a preferable infohash is correctly retrieved.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

    assert layer.get_preferable(b"\x00" * 20) == b"\x00" * 20


def test_get_preferable_already_best(layer: UserActivityLayer) -> None:
    """
    Test if a infohash returns itself when it is preferable.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

    assert layer.get_preferable(b"\x01" * 20) == b"\x00" * 20


def test_get_preferable_unknown(layer: UserActivityLayer) -> None:
    """
    Test if a infohash returns itself when it has no known preferable infohashes.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20)})

    assert layer.get_preferable(b"\x02" * 20) == b"\x02" * 20


def test_get_random(layer: UserActivityLayer) -> None:
    """
    Test if the preferred infohash always gets returned from a random checked selection.
    """
    layer.store("test query", InfoHash(b"\x00" * 20), {InfoHash(b"\x01" * 20), InfoHash(b"\x02" * 20)})
    layer.store("test query", InfoHash(b"\x01" * 20), {InfoHash(b"\x00" * 20), InfoHash(b"\x02" * 20)})

    random_selection = layer.get_preferable_to_random(limit=1)

    assert len(random_selection) == 1
    assert list(random_selection)[0] == b"\x01" * 20
