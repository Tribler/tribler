from __future__ import absolute_import

from Tribler.Test.test_as_server import TestAsServer


class TestTrackerManager(TestAsServer):

    def setUpPreSession(self):
        super(TestTrackerManager, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @property
    def tracker_manager(self):
        return self.session.lm.tracker_manager

    def test_add_tracker(self):
        """
        Test whether adding a tracker works correctly
        """
        self.tracker_manager.add_tracker("http://test1.com")
        self.assertFalse(self.tracker_manager.get_tracker_info("http://test1.com"))

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertTrue(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))

    def test_remove_tracker(self):
        """
        Test whether removing a tracker works correctly
        """
        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertTrue(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))
        self.tracker_manager.remove_tracker("http://test1.com:80/announce")
        self.assertFalse(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))

    def test_get_tracker_info(self):
        """
        Test whether the correct tracker info is returned when requesting it in the tracker manager
        """
        self.assertFalse(self.tracker_manager.get_tracker_info("http://nonexisting.com"))

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertTrue(self.tracker_manager.get_tracker_info("http://test1.com:80/announce"))

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

    def test_get_tracker_for_check(self):
        """
        Test whether the correct tracker is returned when fetching the next eligable tracker for the auto check
        """
        self.assertFalse(self.tracker_manager.get_next_tracker_for_auto_check())

        self.tracker_manager.add_tracker("http://test1.com:80/announce")
        self.assertEqual('http://test1.com/announce', self.tracker_manager.get_next_tracker_for_auto_check())
