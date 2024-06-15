from asyncio import sleep
from binascii import hexlify
from unittest.mock import Mock, call

from ipv8.taskmanager import TaskManager
from ipv8.test.base import TestBase

from tribler.core.notifier import Notification, Notifier
from tribler.core.user_activity.manager import UserActivityManager
from tribler.core.user_activity.types import InfoHash


class TestUserActivityManager(TestBase):
    """
    Tests for the UserActivityManager class.
    """

    def setUp(self) -> None:
        """
        Create a new user activity manager.
        """
        super().setUp()
        self.task_manager = TaskManager()
        self.session = Mock(
            notifier=Notifier(),
            db=Mock(),
            torrent_checker=Mock()
        )
        self.manager = UserActivityManager(self.task_manager, self.session, 500)
        self.task_manager.cancel_pending_task("Check preferable")

    async def tearDown(self) -> None:
        """
        Stop the task manager.
        """
        await self.task_manager.shutdown_task_manager()
        await super().tearDown()

    async def test_notify_local_query_results(self) -> None:
        """
        Test that local query notifications get processed correctly.
        """
        fake_infohashes = [InfoHash(bytes([i]) * 20) for i in range(2)]
        fake_torrent_metadata = [{"infohash": fake_infohashes[i]} for i in range(2)]
        fake_query = "test query"

        self.session.notifier.notify(Notification.local_query_results,
                                     query=fake_query, results=fake_torrent_metadata)
        await sleep(0)

        self.assertIn(fake_query, self.manager.queries)
        self.assertIn(fake_infohashes[0], self.manager.infohash_to_queries)
        self.assertIn(fake_infohashes[1], self.manager.infohash_to_queries)
        self.assertIn(fake_query, self.manager.infohash_to_queries[fake_infohashes[0]])
        self.assertIn(fake_query, self.manager.infohash_to_queries[fake_infohashes[1]])

    async def test_notify_remote_query_results(self) -> None:
        """
        Test that remote query notifications get processed correctly.
        """
        fake_infohashes = [InfoHash(bytes([i]) * 20) for i in range(2)]
        fake_torrent_metadata = [{"infohash": fake_infohashes[i]} for i in range(2)]
        fake_query = "test query"

        self.session.notifier.notify(Notification.remote_query_results,
                                     query=fake_query, results=fake_torrent_metadata, uuid='123', peer=[])
        await sleep(0)

        self.assertIn(fake_query, self.manager.queries)
        self.assertIn(fake_infohashes[0], self.manager.infohash_to_queries)
        self.assertIn(fake_infohashes[1], self.manager.infohash_to_queries)
        self.assertIn(fake_query, self.manager.infohash_to_queries[fake_infohashes[0]])
        self.assertIn(fake_query, self.manager.infohash_to_queries[fake_infohashes[1]])

    async def test_notify_local_query_results_overflow(self) -> None:
        """
        Test that local query notifications do not go beyond the maximum history.
        Old information should be purged. However, infohashes should not be purged if they are still in use.
        """
        self.manager.max_query_history = 1

        fake_infohashes = [InfoHash(bytes([i]) * 20) for i in range(2)]
        fake_torrent_metadata = [{"infohash": fake_infohashes[i]} for i in range(2)]
        fake_query_1 = "test query 1"
        fake_query_2 = "test query 2"

        self.session.notifier.notify(Notification.local_query_results,
                                     query=fake_query_1, results=fake_torrent_metadata)
        await sleep(0)
        self.session.notifier.notify(Notification.local_query_results,
                                     query=fake_query_2, results=fake_torrent_metadata[:1])
        await sleep(0)

        self.assertNotIn(fake_query_1, self.manager.queries)
        self.assertIn(fake_query_2, self.manager.queries)
        self.assertIn(fake_infohashes[0], self.manager.infohash_to_queries)
        self.assertNotIn(fake_infohashes[1], self.manager.infohash_to_queries)
        self.assertNotIn(fake_query_1, self.manager.infohash_to_queries[fake_infohashes[0]])
        self.assertIn(fake_query_2, self.manager.infohash_to_queries[fake_infohashes[0]])
        self.assertNotIn(fake_query_1, self.manager.infohash_to_queries[fake_infohashes[1]])
        self.assertNotIn(fake_query_2, self.manager.infohash_to_queries[fake_infohashes[1]])

    async def test_notify_remote_query_results_overflow(self) -> None:
        """
        Test that remote query notifications do not go beyond the maximum history.
        Old information should be purged. However, infohashes should not be purged if they are still in use.
        """
        self.manager.max_query_history = 1

        fake_infohashes = [InfoHash(bytes([i]) * 20) for i in range(2)]
        fake_torrent_metadata = [{"infohash": fake_infohashes[i]} for i in range(2)]
        fake_query_1 = "test query 1"
        fake_query_2 = "test query 2"

        self.session.notifier.notify(Notification.remote_query_results,
                                     query=fake_query_1, results=fake_torrent_metadata, uuid='123', peer=[])
        await sleep(0)
        self.session.notifier.notify(Notification.remote_query_results,
                                     query=fake_query_2, results=fake_torrent_metadata[:1], uuid='123', peer=[])
        await sleep(0)

        self.assertNotIn(fake_query_1, self.manager.queries)
        self.assertIn(fake_query_2, self.manager.queries)
        self.assertIn(fake_infohashes[0], self.manager.infohash_to_queries)
        self.assertNotIn(fake_infohashes[1], self.manager.infohash_to_queries)
        self.assertNotIn(fake_query_1, self.manager.infohash_to_queries[fake_infohashes[0]])
        self.assertIn(fake_query_2, self.manager.infohash_to_queries[fake_infohashes[0]])
        self.assertNotIn(fake_query_1, self.manager.infohash_to_queries[fake_infohashes[1]])
        self.assertNotIn(fake_query_2, self.manager.infohash_to_queries[fake_infohashes[1]])

    async def test_notify_finished_untracked(self) -> None:
        """
        Test that an untracked infohash does not lead to any information being stored.
        """
        fake_infohash = InfoHash(b'\x00' * 20)
        untracked_fake_infohash = InfoHash(b'\x01' * 20)
        fake_query = "test query"
        self.manager.queries[fake_query] = {fake_infohash}
        self.manager.infohash_to_queries[fake_infohash] = [fake_query]

        self.session.notifier.notify(Notification.torrent_finished,
                                     infohash=hexlify(untracked_fake_infohash).decode(),
                                     name="test torrent",
                                     hidden=False)
        await sleep(0)

        self.assertFalse(self.manager.task_manager.is_pending_task_active("Store query"))
        self.assertEqual(None, self.manager.database_manager.store.call_args)

    async def test_notify_finished_tracked(self) -> None:
        """
        Test that a tracked infohash leads to information being stored.
        """
        fake_infohash = InfoHash(b'\x00' * 20)
        fake_query = "test query"
        self.manager.queries[fake_query] = {fake_infohash}
        self.manager.infohash_to_queries[fake_infohash] = [fake_query]

        self.session.notifier.notify(Notification.torrent_finished,
                                     infohash=hexlify(fake_infohash).decode(), name="test torrent", hidden=False)
        await sleep(0)
        await self.manager.task_manager.wait_for_tasks()

        self.assertEqual(call(fake_query, fake_infohash, set()), self.manager.database_manager.store.call_args)

    async def test_check_preferable_zero(self) -> None:
        """
        Test that checking without available random torrents leads to no checks.
        """
        self.manager.database_manager.get_preferable_to_random = Mock(return_value={})

        self.manager.check_preferable()
        await sleep(0)

        self.assertEqual(None, self.manager.torrent_checker.check_torrent_health.call_args)

    async def test_check_preferable_one(self) -> None:
        """
        Test that checking with one available random torrent leads to one check.
        """
        fake_infohash = InfoHash(b'\x00' * 20)
        self.manager.database_manager.get_preferable_to_random = Mock(return_value={fake_infohash})

        self.manager.check_preferable()
        await sleep(0)

        self.assertEqual(call(fake_infohash), self.manager.torrent_checker.check_torrent_health.call_args)

    async def test_check_preferable_multiple(self) -> None:
        """
        Test that checking with multiple available random torrents leads to as many checks.
        """
        fake_infohashes = {InfoHash(bytes([i]) * 20) for i in range(10)}
        self.manager.database_manager.get_preferable_to_random = Mock(return_value=fake_infohashes)

        self.manager.check_preferable()
        await sleep(0)

        self.assertEqual(10, self.manager.torrent_checker.check_torrent_health.call_count)

    async def test_check(self) -> None:
        """
        Test that checking an infohash schedules a check.
        """
        fake_infohash = InfoHash(b'\x00' * 20)

        self.manager.check(fake_infohash)
        await sleep(0)

        self.assertEqual(call(fake_infohash), self.manager.torrent_checker.check_torrent_health.call_args)
