"""
This file contains the database connection used for the statistics display.
"""
import os
from twisted.internet.defer import inlineCallbacks

from Tribler.community.multichain.database import DATABASE_DIRECTORY
from Tribler.community.multichain.statistics.statistics_database import StatisticsDB
from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock
from Tribler.Test.test_as_server import AbstractServer


class TestStatisticsDatabase(AbstractServer):
    """
    Tests for the trust statistics database connection.
    """

    def __init__(self, *args, **kwargs):
        super(TestStatisticsDatabase, self).__init__(*args, **kwargs)

    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestStatisticsDatabase, self).setUp(annotate=annotate)
        path = os.path.join(self.getStateDir(), DATABASE_DIRECTORY)
        if not os.path.exists(path):
            os.makedirs(path)
        self.db = StatisticsDB(self.getStateDir())
        self.block1 = TestBlock()
        self.block2 = TestBlock()
        self.block3 = TestBlock()

    def test_total_up(self):
        """
        The database should return the correct amount of uploaded data.
        """
        self.block2.total_up = 0

        self.db.add_block(self.block1)
        self.db.add_block(self.block2)

        self.assertEqual(self.block1.total_up, self.db.total_up(self.block1.public_key))
        self.assertEqual(0, self.db.total_up(self.block2.public_key))
        self.assertEqual(0, self.db.total_up(self.block3.public_key))

    def test_total_down(self):
        """
        The database should return the correct amount of downloaded data.
        """
        self.block2.total_down = 0

        self.db.add_block(self.block1)
        self.db.add_block(self.block2)

        self.assertEqual(self.block2.total_down, self.db.total_down(self.block2.public_key))
        self.assertEqual(0, self.db.total_down(self.block2.public_key))
        self.assertEqual(0, self.db.total_down(self.block3.public_key))

    def test_neighbors(self):
        """
        The database should return the correct list of neighbors and the traffic to and from them.
        """
        focus_block1 = TestBlock()
        focus_block2 = TestBlock()

        # All blocks have the same public key
        self.block2.public_key = self.block1.public_key
        self.block3.public_key = self.block1.public_key

        self.block1.link_public_key = focus_block1.public_key
        self.block2.link_public_key = focus_block1.public_key
        self.block3.link_public_key = focus_block2.public_key

        # Add all blocks + one redundant block
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.db.add_block(self.block3)
        self.db.add_block(focus_block1)

        expected_result = {focus_block1.public_key:
                               {"up": self.block1.up + self.block2.up, "down": self.block1.down + self.block2.down},
                           focus_block2.public_key: {"up": self.block3.up, "down": self.block3.down}}

        self.assertDictEqual(expected_result, self.db.neighbor_list(self.block1.public_key))
