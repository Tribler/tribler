from asyncio import Event, sleep
from dataclasses import dataclass
from typing import Generator
from unittest.mock import Mock

from pytest import fixture, mark

from tribler.core import notifications
from tribler.core.components.content_discovery.content_discovery_component import ContentDiscoveryComponent
from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.session import Session
from tribler.core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent
from tribler.core.components.user_activity.types import InfoHash
from tribler.core.components.user_activity.user_activity_component import UserActivityComponent
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.unicode import hexlify


@fixture(name="config")
def fixture_config() -> TriblerConfig:
    return TriblerConfig()


@fixture(name="session")
def fixture_session(config: TriblerConfig) -> Session:
    session = Session(config=config)

    for component in [ContentDiscoveryComponent, LibtorrentComponent, DatabaseComponent, TorrentCheckerComponent]:
        session.components[component] = Mock(started_event=Event(), failed=False)
        session.components[component].started_event.set()

    return session


@fixture(name="component")
async def fixture_component(session) -> Generator[UserActivityComponent, None, None]:
    component = UserActivityComponent(None)
    component.session = session
    await component.run()
    component.task_manager.cancel_pending_task("Check preferable")
    yield component
    await component.shutdown()


@dataclass(unsafe_hash=True)
class TorrentMetadata:
    infohash: InfoHash


@mark.parametrize("notification", [notifications.local_query_results, notifications.remote_query_results])
async def test_notify_query_empty(component: UserActivityComponent, notification) -> None:
    """
    Test that local and remote query notifications without a query get ignored.
    """
    fake_infohashes = [InfoHash(bytes([i]) * 20) for i in range(2)]
    fake_torrent_metadata = [TorrentMetadata(fake_infohashes[i]) for i in range(2)]
    fake_query = None

    component.session.notifier.notify(notification, data={"query": fake_query, "results": fake_torrent_metadata})
    await sleep(0)

    assert fake_query not in component.queries
    assert fake_infohashes[0] not in component.infohash_to_queries
    assert fake_infohashes[1] not in component.infohash_to_queries
    assert fake_query not in component.infohash_to_queries[fake_infohashes[0]]
    assert fake_query not in component.infohash_to_queries[fake_infohashes[1]]


@mark.parametrize("notification", [notifications.local_query_results, notifications.remote_query_results])
async def test_notify_query_results(component: UserActivityComponent, notification) -> None:
    """
    Test that local and remote query notifications get processed correctly.
    """
    fake_infohashes = [InfoHash(bytes([i]) * 20) for i in range(2)]
    fake_torrent_metadata = [TorrentMetadata(fake_infohashes[i]) for i in range(2)]
    fake_query = "test query"

    component.session.notifier.notify(notification, data={"query": fake_query, "results": fake_torrent_metadata})
    await sleep(0)

    assert fake_query in component.queries
    assert fake_infohashes[0] in component.infohash_to_queries
    assert fake_infohashes[1] in component.infohash_to_queries
    assert fake_query in component.infohash_to_queries[fake_infohashes[0]]
    assert fake_query in component.infohash_to_queries[fake_infohashes[1]]


@mark.parametrize("notification", [notifications.local_query_results, notifications.remote_query_results])
async def test_notify_query_results_overflow(component: UserActivityComponent, notification) -> None:
    """
    Test that local and remote query notifications do not go beyond the maximum history.

    Old information should be purged. However, infohashes should not be purged if they are still in use.
    """
    component.max_query_history = 1

    fake_infohashes = [InfoHash(bytes([i]) * 20) for i in range(2)]
    fake_torrent_metadata = [TorrentMetadata(fake_infohashes[i]) for i in range(2)]
    fake_query_1 = "test query 1"
    fake_query_2 = "test query 2"

    component.session.notifier.notify(notification, data={"query": fake_query_1, "results": fake_torrent_metadata})
    await sleep(0)
    component.session.notifier.notify(notification, data={"query": fake_query_2, "results": fake_torrent_metadata[:1]})
    await sleep(0)

    assert fake_query_1 not in component.queries
    assert fake_query_2 in component.queries
    assert fake_infohashes[0] in component.infohash_to_queries
    assert fake_infohashes[1] not in component.infohash_to_queries
    assert fake_query_1 not in component.infohash_to_queries[fake_infohashes[0]]
    assert fake_query_2 in component.infohash_to_queries[fake_infohashes[0]]
    assert fake_query_1 not in component.infohash_to_queries[fake_infohashes[1]]
    assert fake_query_2 not in component.infohash_to_queries[fake_infohashes[1]]


async def test_notify_finished_untracked(component: UserActivityComponent) -> None:
    """
    Test that an untracked infohash does not lead to any information being stored.
    """
    fake_infohash = InfoHash(b'\x00' * 20)
    untracked_fake_infohash = InfoHash(b'\x01' * 20)
    fake_query = "test query"
    component.queries[fake_query] = {fake_infohash}
    component.infohash_to_queries[fake_infohash] = [fake_query]

    component.session.notifier.notify(notifications.torrent_finished,
                                      infohash=hexlify(untracked_fake_infohash), name="test torrent", hidden=False)
    await sleep(0)

    assert not component.task_manager.is_pending_task_active("Store query")
    assert not component.database_manager.store.called


async def test_notify_finished_tracked(component: UserActivityComponent) -> None:
    """
    Test that a tracked infohash leads to information being stored.
    """
    fake_infohash = InfoHash(b'\x00' * 20)
    fake_query = "test query"
    component.queries[fake_query] = {fake_infohash}
    component.infohash_to_queries[fake_infohash] = [fake_query]

    component.session.notifier.notify(notifications.torrent_finished,
                                      infohash=hexlify(fake_infohash), name="test torrent", hidden=False)
    await sleep(0)
    await component.task_manager.wait_for_tasks()

    component.database_manager.store.assert_called_with(fake_query, fake_infohash, set())


async def test_check_preferable_zero(component: UserActivityComponent) -> None:
    """
    Test that checking without available random torrents leads to no checks.
    """
    component.database_manager.get_preferable_to_random = Mock(return_value={})

    component.check_preferable()
    await sleep(0)

    assert not component.torrent_checker.check_torrent_health.called


async def test_check_preferable_one(component: UserActivityComponent) -> None:
    """
    Test that checking with one available random torrent leads to one check.
    """
    fake_infohash = InfoHash(b'\x00' * 20)
    component.database_manager.get_preferable_to_random = Mock(return_value={fake_infohash})

    component.check_preferable()
    await sleep(0)

    component.torrent_checker.check_torrent_health.assert_called_with(fake_infohash)


async def test_check_preferable_multiple(component: UserActivityComponent) -> None:
    """
    Test that checking with multiple available random torrents leads to as many checks.
    """
    fake_infohashes = {InfoHash(bytes([i]) * 20) for i in range(10)}
    component.database_manager.get_preferable_to_random = Mock(return_value=fake_infohashes)

    component.check_preferable()
    await sleep(0)

    assert component.torrent_checker.check_torrent_health.call_count == 10
