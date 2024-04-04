from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from ipv8.test.base import TestBase

from tribler.core.libtorrent.trackers import get_uniformed_tracker_url
from tribler.core.torrent_checker.tracker_manager import TrackerManager
from tribler.test_unit.core.torrent_checker.mocks import MockTrackerState


class MockTrackerManager(TrackerManager):
    """
    A mocked TrackerManager that does not perform file io with the blacklist file.
    """

    def __init__(self) -> None:
        """
        Create a new MockTrackerManager.
        """
        self.blacklist_contents = None
        super().__init__(Path("."), Mock(TrackerState=MockTrackerState()))

    def load_blacklist(self) -> None:
        """
        Load the blacklist.
        """
        if self.blacklist_contents:
            self.blacklist.extend([get_uniformed_tracker_url(url) for url in self.blacklist_contents.split("\n")])


class TestTrackerManager(TestBase):
    """
    Tests for the TrackerManager class.
    """

    def setUp(self) -> None:
        """
        Create a new TrackerManager.
        """
        self.tracker_manager = MockTrackerManager()
        MockTrackerState.instances = []

    def test_add_tracker_invalid(self) -> None:
        """
        Test if adding an invalid tracker works correctly.
        """
        self.tracker_manager.add_tracker("http://test1.com")

        self.assertIsNone(self.tracker_manager.get_tracker_info("http://test1.com"))

    def test_add_tracker_valid(self) -> None:
        """
        Test if adding a valid tracker works correctly.
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")

        self.assertIsNotNone(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))

    def test_remove_tracker(self) -> None:
        """
        Test if removing a tracker works correctly.
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.remove_tracker("http://test1.com:80/announce")

        self.assertIsNone(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))

    def test_update_tracker_info_non_existent(self) -> None:
        """
        Test if a non-existent tracker's info is not updated.
        """
        self.tracker_manager.update_tracker_info("http://nonexisting.com", True)

        self.assertIsNone(self.tracker_manager.get_tracker_info("http://nonexisting.com"))

    def test_update_tracker_info_failed(self) -> None:
        """
        Test if the tracker info update failure is correctly updated.
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.update_tracker_info("http://test1.com/announce", False)

        tracker_info = self.tracker_manager.get_tracker_info("http://test1.com/announce")
        self.assertIsNotNone(tracker_info)
        self.assertEqual(1, tracker_info['failures'])

    def test_update_tracker_info_success(self) -> None:
        """
        Test if the tracker info update success is correctly updated.
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.update_tracker_info("http://test1.com/announce", True)

        tracker_info = self.tracker_manager.get_tracker_info("http://test1.com/announce")
        self.assertTrue(tracker_info['is_alive'])

    def test_get_tracker_for_check_unknown(self) -> None:
        """
        Test if the no tracker is returned when fetching from no eligible trackers.
        """
        self.assertIsNone(self.tracker_manager.get_next_tracker())

    def test_get_tracker_for_check_known(self) -> None:
        """
        Test if the correct tracker is returned when fetching the next eligible tracker for the auto check.
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertEqual("http://test1.com/announce", self.tracker_manager.get_next_tracker().url)

    def test_get_tracker_for_check_blacklist(self) -> None:
        """
        Test if the next tracker for autocheck is not in the blacklist.
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.blacklist.append("http://test1.com/announce")

        self.assertIsNone(self.tracker_manager.get_next_tracker())

    def test_load_blacklist_from_file_none(self) -> None:
        """
        Test if we correctly load a blacklist without entries.
        """
        self.tracker_manager.blacklist_contents = ""
        self.tracker_manager.load_blacklist()

        self.assertEqual([], self.tracker_manager.blacklist)

    def test_load_blacklist_from_file_single(self) -> None:
        """
        Test if we correctly load a blacklist entry from a file.
        """
        self.tracker_manager.blacklist_contents = "http://test1.com/announce"
        self.tracker_manager.load_blacklist()

        self.assertIn("http://test1.com/announce", self.tracker_manager.blacklist)

    def test_load_blacklist_from_file_multiple(self) -> None:
        """
        Test if we correctly load blacklist entries from a file.
        """
        self.tracker_manager.blacklist_contents = "http://test1.com/announce\nhttp://test2.com/announce"
        self.tracker_manager.load_blacklist()

        self.assertIn("http://test1.com/announce", self.tracker_manager.blacklist)
        self.assertIn("http://test2.com/announce", self.tracker_manager.blacklist)
