from Tribler.Core.Modules.tracker_manager import TrackerManager
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTrackerManager(TriblerCoreTest):

    def setUpPreSession(self):
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())

    def setUp(self, annotate=True):
        super(TestTrackerManager, self).setUp(annotate=annotate)

        self.setUpPreSession()
        self.session = Session(self.config, ignore_singleton=True)
        self.session.start_database()
        self.tracker_manager = TrackerManager(self.session)

    @blocking_call_on_reactor_thread
    def test_initialize(self):
        """
        Test the initialization of the tracker manager
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.add_tracker("http://test2.com:80/announce")
        self.tracker_manager.initialize()
        self.assertEqual(len(self.tracker_manager._tracker_dict.keys()), 4)
        self.assertTrue("http://test1.com/announce" in self.tracker_manager._tracker_dict)
        self.assertTrue("http://test2.com/announce" in self.tracker_manager._tracker_dict)

    @blocking_call_on_reactor_thread
    def test_add_tracker(self):
        """
        Test whether adding a tracker works correctly
        """
        self.tracker_manager.add_tracker("http://test1.com")
        self.assertEqual(len(self.tracker_manager._tracker_dict), 0)

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertEqual(len(self.tracker_manager._tracker_dict), 1)

        # Add the same URL again, it shouldn't be inserted
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertEqual(len(self.tracker_manager._tracker_dict), 1)

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
        self.assertEqual(len(self.tracker_manager._tracker_dict), 0)

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.update_tracker_info("http://test1.com/announce", False)
        self.assertEqual(self.tracker_manager._tracker_dict["http://test1.com/announce"]['failures'], 1)
        self.tracker_manager.update_tracker_info("http://test1.com/announce", True)
        self.assertTrue(self.tracker_manager._tracker_dict["http://test1.com/announce"]['is_alive'])

    @blocking_call_on_reactor_thread
    def test_should_check_tracker(self):
        """
        Test whether we should check a tracker or not
        """
        self.assertTrue(self.tracker_manager.should_check_tracker("http://nonexisting.com"))

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager.update_tracker_info("http://test1.com/announce", False)
        self.assertFalse(self.tracker_manager.should_check_tracker("http://test1.com/announce"))

    @blocking_call_on_reactor_thread
    def test_get_tracker_for_check(self):
        """
        Test whether the correct tracker is returned when fetching the next eligable tracker for the auto check
        """
        self.assertFalse(self.tracker_manager.get_next_tracker_for_auto_check())
        self.tracker_manager.initialize()
        self.assertEqual('DHT', self.tracker_manager.get_next_tracker_for_auto_check()[0])

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.tracker_manager._tracker_dict["http://test1.com/announce"]['last_check'] = 0
        self.tracker_manager._tracker_dict["DHT"]['last_check'] = 1000
        self.assertEqual('http://test1.com/announce', self.tracker_manager.get_next_tracker_for_auto_check()[0])
