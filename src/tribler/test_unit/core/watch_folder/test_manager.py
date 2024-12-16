import os.path
from asyncio import sleep
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call, patch

from ipv8.taskmanager import TaskManager
from ipv8.test.base import TestBase

from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.watch_folder.manager import WatchFolderManager
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT
from tribler.test_unit.mocks import MockTriblerConfigManager


class TestWatchFolderManager(TestBase):
    """
    Tests for the Notifier class.
    """

    def setUp(self) -> None:
        """
        Create a new versioning manager.
        """
        super().setUp()
        self.config = MockTriblerConfigManager()
        self.task_manager = TaskManager()
        self.manager = WatchFolderManager(Mock(config=self.config, download_manager=Mock(
            start_download=AsyncMock(), remove_download=AsyncMock())), self.task_manager)

    async def tearDown(self) -> None:
        """
        Shut down our task manager.
        """
        await self.task_manager.shutdown_task_manager()
        await super().tearDown()

    def test_watch_folder_not_dir(self) -> None:
        """
        Test that the watch folder is disabled when the "directory" setting is not a directory.
        """
        self.config.set("watch_folder/enabled", True)
        self.config.set("watch_folder/directory", "")

        result = self.manager.check()

        self.assertFalse(result)

    def test_watch_folder_invalid_dir(self) -> None:
        """
        Test that the watch folder is disabled when the directory is invalid.
        """
        self.config.set("watch_folder/enabled", True)
        self.config.set("watch_folder/directory", "BFLKJAELKJRLAKJDLAGKjLjgaEPGJAPEJGPAIJEPGIAPDJG")

        result = self.manager.check()

        self.assertFalse(result)

    async def test_watch_folder_no_files(self) -> None:
        """
        Test that in the case of an empty folder, downloads are not started.
        """
        self.config.set("watch_folder/enabled", True)
        self.config.set("watch_folder/directory", os.path.dirname(__file__))

        with patch("os.walk", lambda _: []):
            result = self.manager.check()
        await sleep(0)
        scheduled_tasks = self.task_manager.get_tasks()

        self.assertTrue(result)
        self.assertEqual(0, len(scheduled_tasks))

    async def test_watch_folder_no_torrent_file(self) -> None:
        """
        Test that in the case of a folder without torrents, downloads are not started.
        """
        self.config.set("watch_folder/enabled", True)
        self.config.set("watch_folder/directory", os.path.dirname(__file__))

        result = self.manager.check()
        await sleep(0)
        scheduled_tasks = self.task_manager.get_tasks()

        self.assertTrue(result)
        self.assertEqual(0, len(scheduled_tasks))

    async def test_watch_folder_torrent_file_start_download(self) -> None:
        """
        Test that in the case of presence of a torrent file, a download is started.
        """
        self.config.set("watch_folder/enabled", True)
        self.config.set("watch_folder/directory", os.path.dirname(__file__))
        self.manager.session.download_manager.download_exists = lambda _: False
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)

        with patch("os.walk", lambda _: [(".", [], ["fake.torrent"])]), \
                patch.object(TorrentDef, "load", AsyncMock(return_value=tdef)):
            result = self.manager.check()
            await sleep(0)  # Schedule processing
            scheduled_tasks = self.task_manager.get_tasks()
            await sleep(0)  # Process (i.e., start the download)

        self.assertTrue(result)
        self.assertEqual(1, len(scheduled_tasks))
        self.assertEqual(call(torrent_file=Path("fake.torrent"), tdef=tdef),
                         self.manager.session.download_manager.start_download.call_args)

    async def test_watch_folder_torrent_file_start_download_existing(self) -> None:
        """
        Test that in the case of presence of a torrent file, a download is started twice.
        """
        self.config.set("watch_folder/enabled", True)
        self.config.set("watch_folder/directory", os.path.dirname(__file__))
        self.manager.session.download_manager.download_exists = lambda _: True
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)

        with patch("os.walk", lambda _: [(".", [], ["fake.torrent"])]), \
                patch.object(TorrentDef, "load", AsyncMock(return_value=tdef)):
            result = self.manager.check()
            await sleep(0)  # Schedule processing
            scheduled_tasks = self.task_manager.get_tasks()
            await sleep(0)  # Process (i.e., start the download)

        self.assertTrue(result)
        self.assertEqual(1, len(scheduled_tasks))
        self.assertIsNone(self.manager.session.download_manager.start_download.call_args)

    async def test_watch_folder_no_crash_exception(self) -> None:
        """
        Test that errors raised during processing do not crash us.
        """
        self.config.set("watch_folder/enabled", True)
        self.config.set("watch_folder/directory", os.path.dirname(__file__))
        self.manager.session.download_manager.start_download = AsyncMock(side_effect=RuntimeError)
        self.manager.session.download_manager.download_exists = lambda _: False
        tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)

        with patch("os.walk", lambda _: [(".", [], ["fake.torrent"])]), \
                patch.object(TorrentDef, "load", AsyncMock(return_value=tdef)):
            result = self.manager.check()
            await sleep(0)  # Schedule processing
            scheduled_tasks = self.task_manager.get_tasks()
            await sleep(0)  # Process (i.e., start the download)

        self.assertTrue(result)
        self.assertEqual(1, len(scheduled_tasks))
        self.assertEqual(call(torrent_file=Path("fake.torrent"), tdef=tdef),
                         self.manager.session.download_manager.start_download.call_args)
