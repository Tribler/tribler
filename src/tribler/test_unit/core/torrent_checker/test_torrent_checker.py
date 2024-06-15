from __future__ import annotations

import random
import secrets
import time
from binascii import unhexlify
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from ipv8.test.base import TestBase
from ipv8.util import succeed

import tribler
from tribler.core.notifier import Notification, Notifier
from tribler.core.torrent_checker.dataclasses import (
    TOLERABLE_TIME_DRIFT,
    HealthInfo,
    TrackerResponse,
)
from tribler.core.torrent_checker.torrent_checker import (
    TORRENT_SELECTION_POOL_SIZE,
    TorrentChecker,
    aggregate_responses_for_infohash,
)
from tribler.core.torrent_checker.torrentchecker_session import HttpTrackerSession, UdpSocketManager
from tribler.core.torrent_checker.tracker_manager import TrackerManager
from tribler.test_unit.core.torrent_checker.mocks import MockEntity, MockTorrentState, MockTrackerState
from tribler.tribler_config import TriblerConfigManager


class MockMiniTorrentMetadata(MockEntity):
    """
    A partial mock of TorrentMetadata.
    """

    instances = []

    def __init__(self, infohash: bytes = b"", title: str = "", health: MockTorrentState | None = None) -> None:
        """
        Create a new MockMiniTorrentMetadata.
        """
        self.__class__.instances.append(self)

        self.title = title
        self.infohash = infohash
        self.health = health


class TestTorrentChecker(TestBase):
    """
    Tests for the TorrentChecker class.
    """

    def setUp(self) -> None:
        """
        Create a new tracker manager and a torrent checker.
        """
        super().setUp()

        self.metadata_store = Mock()
        self.metadata_store.TorrentState = MockTorrentState()
        self.metadata_store.TrackerState = MockTrackerState()
        self.metadata_store.TorrentMetadata = MockMiniTorrentMetadata()
        self.metadata_store.TorrentState.__class__.instances = []
        self.metadata_store.TrackerState.__class__.instances = []
        self.metadata_store.TorrentMetadata.__class__.instances = []

        self.tracker_manager = TrackerManager(state_dir=Path("."), metadata_store=self.metadata_store)
        self.torrent_checker = TorrentChecker(config=TriblerConfigManager(), tracker_manager=self.tracker_manager,
                                              download_manager=MagicMock(get_metainfo=AsyncMock()),
                                              notifier=MagicMock(), metadata_store=self.metadata_store)

    async def tearDown(self) -> None:
        """
        Shut doown the torrent checker.
        """
        await self.torrent_checker.shutdown()
        await super().tearDown()

    async def test_create_socket_fail(self) -> None:
        """
        Test creation of the UDP socket of the torrent checker when it fails.
        """

        def mocked_listen_on_udp() -> None:
            message = "Something went wrong"
            raise OSError(message)

        self.torrent_checker.socket_mgr = UdpSocketManager()
        self.torrent_checker.listen_on_udp = mocked_listen_on_udp
        await self.torrent_checker.create_socket_or_schedule()

        self.assertIsNone(self.torrent_checker.udp_transport)
        self.assertTrue(self.torrent_checker.is_pending_task_active("listen_udp_port"))

    async def test_health_check_blacklisted_trackers(self) -> None:
        """
        Test if only cached results of a torrent are returned with only blacklisted trackers.
        """
        tracker, = self.torrent_checker.mds.TrackerState.instances = [MockTrackerState(url="http://localhost/tracker")]
        self.torrent_checker.mds.TorrentState.instances = [MockTorrentState(infohash=b'a' * 20, seeders=5, leechers=10,
                                                                            trackers={tracker},
                                                                            last_check=int(time.time()))]
        self.torrent_checker.tracker_manager.blacklist.append("http://localhost/tracker")

        result = await self.torrent_checker.check_torrent_health(b'a' * 20)

        self.assertEqual(5, result.seeders)
        self.assertEqual(10, result.leechers)

    async def test_health_check_cached(self) -> None:
        """
        Test whether cached results of a torrent are returned when fetching the health of a torrent.
        """
        tracker, = self.torrent_checker.mds.TrackerState.instances = [MockTrackerState(url="http://localhost/tracker")]
        self.torrent_checker.mds.TorrentState.instances = [MockTorrentState(infohash=b'a' * 20, seeders=5, leechers=10,
                                                                            trackers={tracker},
                                                                            last_check=int(time.time()))]

        result = await self.torrent_checker.check_torrent_health(b'a' * 20)

        self.assertEqual(5, result.seeders)
        self.assertEqual(10, result.leechers)

    def test_load_torrents_check_from_db_no_self_checked(self) -> None:
        """
        Test if the torrents_checked only considers self-checked torrents.
        """
        self.torrent_checker.mds.TorrentState.instances = [MockTorrentState(infohash=secrets.token_bytes(20),
                                                                            seeders=random.randint(1, 100),
                                                                            leechers=random.randint(1, 100),
                                                                            last_check=int(time.time()),
                                                                            self_checked=False)
                                                           for _ in range(10)]

        self.assertEqual(0, len(self.torrent_checker.torrents_checked))

    def test_load_torrents_check_from_db_only_fresh(self) -> None:
        """
        Test if the torrents_checked only considers fresh torrents.
        """
        self.torrent_checker.mds.TorrentState.instances = [MockTorrentState(infohash=secrets.token_bytes(20),
                                                                            seeders=random.randint(1, 100),
                                                                            leechers=random.randint(1, 100),
                                                                            last_check=0,
                                                                            self_checked=True)
                                                           for _ in range(10)]

        self.assertEqual(0, len(self.torrent_checker.torrents_checked))

    def test_load_torrents_check_from_db_allow_fresh_self_checked(self) -> None:
        """
        Test if the torrents_checked does consider fresh self-checked torrents.
        """
        self.torrent_checker.mds.TorrentState.instances = [MockTorrentState(infohash=secrets.token_bytes(20),
                                                                            seeders=random.randint(1, 100),
                                                                            leechers=random.randint(1, 100),
                                                                            last_check=int(time.time()),
                                                                            self_checked=True)
                                                           for _ in range(10)]

        self.assertEqual(10, len(self.torrent_checker.torrents_checked))

    async def test_task_select_no_tracker(self) -> None:
        """
        Test if we are not checking a random tracker when there are no trackers in the database.
        """
        result = await self.torrent_checker.check_random_tracker()

        self.assertIsNone(result)

    async def test_check_random_tracker_shutdown(self) -> None:
        """
        Test if we are not performing a tracker check when we are shutting down.
        """
        await self.torrent_checker.shutdown()

        result = await self.torrent_checker.check_random_tracker()

        self.assertIsNone(result)

    async def test_check_random_tracker_not_alive(self) -> None:
        """
        Test if we correctly update the tracker state when the number of failures is too large.
        """
        self.torrent_checker.mds.TrackerState.instances = [MockTrackerState(url="http://localhost/tracker",
                                                                            failures=1000, alive=True)]

        tracker = self.torrent_checker.tracker_manager.TrackerState.get(lambda x: True)

        self.assertTrue(tracker.alive)

    async def test_task_select_tracker(self) -> None:
        """
        Test if a random tracker can be selected.
        """
        tracker, = self.torrent_checker.mds.TrackerState.instances = [MockTrackerState(url="http://localhost/tracker")]
        self.torrent_checker.mds.TorrentState.instances = [MockTorrentState(infohash=b'a' * 20, seeders=5, leechers=10,
                                                                            trackers={tracker})]

        controlled_session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5, None)
        controlled_session.connect_to_tracker = lambda: succeed(None)

        self.torrent_checker.create_session_for_request = lambda *args, **kwargs: controlled_session

        with patch.dict(tribler.core.torrent_checker.torrent_checker.__dict__,
                        {"select": (lambda x: self.torrent_checker.mds.TorrentState.instances)}):
            result = await self.torrent_checker.check_random_tracker()

        self.assertIsNone(result)
        self.assertEqual(1, len(controlled_session.infohash_list))

        await controlled_session.cleanup()

    async def test_tracker_test_error_resolve(self) -> None:
        """
        Test if we capture the error when a tracker check fails.
        """
        tracker, = self.tracker_manager.TrackerState.instances = [MockTrackerState(url="http://localhost/tracker")]
        self.torrent_checker.mds.TorrentState.instances = [
            MockTorrentState(infohash=b'a' * 20, seeders=5, leechers=10, trackers={tracker},
                             last_check=int(time.time()))
        ]

        with patch.dict(tribler.core.torrent_checker.torrent_checker.__dict__,
                        {"select": (lambda x: self.torrent_checker.mds.TorrentState.instances)}):
            result = await self.torrent_checker.check_random_tracker()

        self.assertIsNone(result)
        self.assertEqual({}, self.torrent_checker.sessions)

    async def test_tracker_no_infohashes(self) -> None:
        """
        Test if the check of a tracker without associated torrents leads to no result.
        """
        self.torrent_checker.tracker_manager.add_tracker('http://trackertest.com:80/announce')

        with patch.dict(tribler.core.torrent_checker.torrent_checker.__dict__,
                        {"select": (lambda x: self.torrent_checker.mds.TorrentState.instances)}):
            result = await self.torrent_checker.check_random_tracker()

        self.assertIsNone(result)

    def test_get_valid_next_tracker_for_auto_check(self) -> None:
        """
        Test if only valid tracker url are used for auto check.
        """
        self.tracker_manager.TrackerState.instances = [
            MockTrackerState("http://anno nce.torrentsmd.com:8080/announce"),
            MockTrackerState("http://announce.torrentsmd.com:8080/announce"),
        ]

        next_tracker = self.torrent_checker.get_next_tracker()

        self.assertEqual("http://announce.torrentsmd.com:8080/announce", next_tracker.url)

    def test_update_health(self) -> None:
        """
        Test if torrent health can be updated.
        """
        responses = [
            TrackerResponse("udp://localhost:2801", [HealthInfo(b"\xee" * 20, leechers=1, seeders=2)]),
            TrackerResponse("DHT", [HealthInfo(b"\xee" * 20, leechers=12, seeders=13)])
        ]
        health = aggregate_responses_for_infohash(b"\xee" * 20, responses)
        health.self_checked = True
        ts = MockTorrentState(infohash=b"\xee" * 20)
        self.torrent_checker.mds.TorrentState.instances = [ts]

        updated = self.torrent_checker.update_torrent_health(health)

        self.assertIsNotNone(updated)
        self.assertEqual(1, len(self.torrent_checker.torrents_checked))
        self.assertEqual(12, ts.leechers)
        self.assertEqual(13, ts.seeders)

    async def test_check_local_torrents(self) -> None:
        """
        Test if the random torrent health checking mechanism picks the right torrents.
        """
        self.torrent_checker.mds.TorrentState.instances = [
            MockTorrentState(bytes([i]) * 20, i, last_check=int(time.time()) if i < 20 else 0) for i in range(40)
        ]
        self.torrent_checker.mds.TorrentMetadata.instances = [
            MockMiniTorrentMetadata(bytes([i]) * 20, f'torrent{i}', self.torrent_checker.mds.TorrentState.instances[i])
            for i in range(40)
        ]
        stale_infohashes = [bytes([i]) * 20 for i in range(20, 40)]

        # 1. Popular torrents are in the front, and
        # 2. Older torrents are towards the back
        selection_range = (stale_infohashes[0:TORRENT_SELECTION_POOL_SIZE]
                           + stale_infohashes[-TORRENT_SELECTION_POOL_SIZE:])
        selected_torrents, _ = await self.torrent_checker.check_local_torrents()

        self.assertLessEqual(len(selected_torrents), TORRENT_SELECTION_POOL_SIZE)
        for t in selected_torrents:
            self.assertIn(t.infohash, selection_range)

    def test_update_torrent_health_invalid_health(self) -> None:
        """
        Tests if invalid health is ignored in TorrentChecker.update_torrent_health().
        """
        health = HealthInfo(unhexlify('abcd0123'), last_check=int(time.time()) + TOLERABLE_TIME_DRIFT + 2)

        self.assertFalse(self.torrent_checker.update_torrent_health(health))

    def test_update_torrent_health_not_self_checked(self) -> None:
        """
        Tests if non-self-checked health is ignored in TorrentChecker.update_torrent_health().
        """
        health = HealthInfo(unhexlify('abcd0123'))

        self.assertFalse(self.torrent_checker.update_torrent_health(health))

    def test_update_torrent_health_unknown_torrent(self) -> None:
        """
        Tests if unknown torrent's health is ignored in TorrentChecker.update_torrent_health().
        """
        health = HealthInfo(unhexlify('abcd0123'), 1, 2, self_checked=True)

        self.assertFalse(self.torrent_checker.update_torrent_health(health))

    async def test_update_torrent_health_no_replace(self) -> None:
        """
        Tests if the TorrentChecker.notify() method is called even if the new health does not replace the old health.
        """
        now = int(time.time())
        mocked_handler = Mock()
        self.torrent_checker.notifier = Notifier()
        self.torrent_checker.notifier.add(Notification.torrent_health_updated, mocked_handler)
        self.torrent_checker.mds.TorrentState.instances = [MockTorrentState(infohash=unhexlify('abcd0123'), seeders=2,
                                                                            leechers=1, last_check=now,
                                                                            self_checked=True)]
        prev_health = self.torrent_checker.mds.TorrentState.instances[0].to_health()

        health = HealthInfo(unhexlify('abcd0123'), 1, 2, self_checked=True, last_check=now)

        self.assertFalse(self.torrent_checker.update_torrent_health(health))

        notified = mocked_handler.call_args.kwargs
        self.assertEqual(prev_health.infohash, unhexlify(notified["infohash"]))
        self.assertEqual(prev_health.seeders, notified["num_seeders"])
        self.assertEqual(prev_health.leechers, notified["num_leechers"])
        self.assertEqual(prev_health.last_check, notified["last_tracker_check"])
