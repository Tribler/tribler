from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Modules.tracker_manager import TrackerManager
from Tribler.Core.Session import Session
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTrackerManager(TriblerCoreTest):

    def setUpPreSession(self):
        self.config = TriblerConfig()
        self.config.set_state_dir(self.getStateDir())

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestTrackerManager, self).setUp(annotate=annotate)

        self.setUpPreSession()
        self.session = Session(self.config, ignore_singleton=True)
        self.session.start_database()
        self.tracker_manager = TrackerManager(self.session)

    @blocking_call_on_reactor_thread
    def test_add_tracker(self):
        """
        Test whether adding a tracker works correctly
        """
        self.tracker_manager.add_tracker("http://test1.com")
        self.assertFalse(self.tracker_manager.get_tracker_info("http://test1.com"))

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertTrue(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))

    @blocking_call_on_reactor_thread
    def test_get_tracker_info(self):
        """
        Test whether the correct tracker info is returned when requesting it in the tracker manager
        """
        self.assertFalse(self.tracker_manager.get_tracker_info("http://nonexisting.com"))

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertTrue(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))

    @blocking_call_on_reactor_thread
    def test_update_tracker_info(self):
        """
        Test whether the tracker info is correctly updated
        """
        self.tracker_manager.update_tracker_info("http://nonexisting.com", True)
        self.assertFalse(self.tracker_manager.get_tracker_info("http://nonexisting.com"))

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.update_tracker_info("http://test1.com/announce", False)

        tracker_info = self.tracker_manager.get_tracker_info("http://test1.com/announce")
        self.assertTrue(tracker_info)
        self.assertEqual(tracker_info['failures'], 1)

        self.tracker_manager.update_tracker_info("http://test1.com/announce", True)
        tracker_info = self.tracker_manager.get_tracker_info("http://test1.com/announce")
        self.assertTrue(tracker_info['is_alive'])

    @blocking_call_on_reactor_thread
    def test_get_tracker_for_check(self):
        """
        Test whether the correct tracker is returned when fetching the next eligable tracker for the auto check
        """
        self.assertFalse(self.tracker_manager.get_next_tracker_for_auto_check())

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertEqual('http://test1.com/announce', self.tracker_manager.get_next_tracker_for_auto_check())
