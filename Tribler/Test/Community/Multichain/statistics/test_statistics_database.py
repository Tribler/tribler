"""
This file contains the test case for the statistics display.

Both the network node and the database driver are tested in this file.
"""
from twisted.internet.defer import inlineCallbacks

from Tribler.community.multichain.statistics.database_driver import DatabaseDriver
from Tribler.Test.test_as_server import BaseTestCase


class TestStatisticsDatabase(BaseTestCase):
    """
    Test class for the statistics display database connection.
    """

    @inlineCallbacks
    def setUp(self):
        """
        Setup for the test case.

        :return: test class for the database connection.
        """
        yield super(TestStatisticsDatabase, self).setUp()
        self.driver = DatabaseDriver()
        self.focus_pk = "30"
        self.edge_pk_a = "61"
        self.edge_pk_b = "62"
        self.fake_pk = "0"

    def test_get_neighbors(self):
        """
        The network node should return the correct list of neighbors.
        """
        expected_result_focus = {u"31": {"up": 28, "down": 54},
                                 u"32": {"up": 126, "down": 27},
                                 u"33": {"up": 34, "down": 302},
                                 u"34": {"up": 59, "down": 580}}
        expected_result_fake = {}

        result_dict_focus = self.driver.neighbor_list(self.focus_pk)
        result_dict_fake = self.driver.neighbor_list(self.fake_pk)

        self.assertDictEqual(expected_result_focus, result_dict_focus)
        self.assertDictEqual(expected_result_fake, result_dict_fake)

    def test_total_up(self):
        """
        The node should return the right amount of uploaded data.
        """
        focus_up = self.driver.total_up(self.focus_pk)
        self.assertEqual(focus_up, 247)

        only_up = self.driver.total_up(self.edge_pk_b)
        only_down = self.driver.total_up(self.edge_pk_a)
        fake_up = self.driver.total_up(self.fake_pk)

        self.assertEqual(only_up, 5)
        self.assertEqual(only_down, 2)
        self.assertEqual(fake_up, 0)

    def test_total_down(self):
        """
        The node should return the right amount of downloaded data.
        """
        focus_down = self.driver.total_down(self.focus_pk)
        self.assertEqual(focus_down, 963)

        only_down = self.driver.total_down(self.edge_pk_a)
        only_up = self.driver.total_down(self.edge_pk_b)
        fake_down = self.driver.total_down(self.fake_pk)

        self.assertEqual(only_down, 10)
        self.assertEqual(only_up, 1)
        self.assertEqual(fake_down, 0)
