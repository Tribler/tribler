from binascii import hexlify, unhexlify
import os

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.Triblerchain.test_triblerchain_utilities import TriblerTestBlock
from Tribler.Test.Community.Trustchain.test_trustchain_utilities import TrustChainTestCase
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.triblerchain.database import TriblerChainDB, LATEST_TRIBLERCHAIN_AGGREGATES_VERSION
from Tribler.community.trustchain.database import DATABASE_DIRECTORY
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestDatabase(TrustChainTestCase):
    """
    Tests the Database for TriblerChain database.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestDatabase, self).setUp(annotate=annotate)
        path = os.path.join(self.getStateDir(), DATABASE_DIRECTORY)
        if not os.path.exists(path):
            os.makedirs(path)
        self.db = TriblerChainDB(self.getStateDir(), u'triblerchain')
        self.block1 = TriblerTestBlock(transaction={'up': 42, 'down': 13})
        self.block2 = TriblerTestBlock(transaction={'up': 46, 'down': 12})
        self.block3 = TriblerTestBlock(transaction={'up': 11, 'down': 23})

    @blocking_call_on_reactor_thread
    def set_db_version(self, database_version, aggregate_version):
        """
        Update the version of the database.

        :param database_version: the new version of the database
        :param aggregate_version: the new version of the aggregate table
        """
        self.db.executescript(u"UPDATE option SET value = '%d' WHERE key = 'database_version';" % database_version)
        self.db.executescript(u"UPDATE option SET value = '%d' WHERE key = 'aggregate_version';" % aggregate_version)
        self.db.close(commit=True)
        self.db = TriblerChainDB(self.getStateDir(), u'triblerchain')

    @blocking_call_on_reactor_thread
    def test_get_num_interactors(self):
        """
        Test whether the right number of interactors is returned
        """
        self.block2 = TriblerTestBlock(previous=self.block1, transaction={'up': 42, 'down': 42,
                                                                          "total_up": 42, "total_down": 42})
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.assertEqual((2, 2), self.db.get_num_unique_interactors(self.block1.public_key))

    @blocking_call_on_reactor_thread
    def test_insert_aggregate_block(self):
        """
        Test whether statistics blocks are inserted correctly.
        """
        self.block1.public_key = unhexlify("00")
        self.block1.link_public_key = unhexlify("ff")
        self.db.insert_aggregate_block(self.block1)

        # Test for the first block
        rows = self.db.execute(
            u"SELECT public_key_a, public_key_b, traffic_a_to_b, traffic_b_to_a FROM triblerchain_aggregates", ()
        ).fetchall()

        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(hexlify(self.block1.public_key), str(row[0]))
        self.assertEqual(hexlify(self.block1.link_public_key), str(row[1]))
        self.assertEqual(self.block1.transaction["up"], row[2])
        self.assertEqual(self.block1.transaction["down"], row[3])

        # Test after adding second block between same users
        self.block2.public_key = self.block1.link_public_key
        self.block2.link_public_key = self.block1.public_key
        self.db.insert_aggregate_block(self.block2)

        rows = self.db.execute(
            u"SELECT public_key_a, public_key_b, traffic_a_to_b, traffic_b_to_a FROM triblerchain_aggregates", ()
        ).fetchall()

        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(hexlify(self.block1.public_key), str(row[0]))
        self.assertEqual(hexlify(self.block1.link_public_key), str(row[1]))
        self.assertEqual(self.block1.transaction["up"] + self.block2.transaction["down"], row[2])
        self.assertEqual(self.block1.transaction["down"] + self.block2.transaction["up"], row[3])

    @blocking_call_on_reactor_thread
    def test_total_traffic(self):
        """
        Test whether the correct amount of traffic is returned.
        """
        self.block1.public_key = unhexlify("00")
        self.block1.link_public_key = unhexlify("11")
        self.block2.public_key = unhexlify("11")
        self.block2.link_public_key = unhexlify("22")
        self.block3.public_key = unhexlify("ff")
        self.block3.link_public_key = unhexlify("33")

        self.db.insert_aggregate_block(self.block1)
        self.db.insert_aggregate_block(self.block2)
        self.db.insert_aggregate_block(self.block3)

        pk_1_up, pk_1_down, pk_1_neigh = self.db.total_traffic("11")
        pk_f_up, pk_f_down, pk_f_neigh = self.db.total_traffic("ff")
        fake_up, fake_down, fake_neigh = self.db.total_traffic("aa")

        # Multiple links
        self.assertEqual(self.block1.transaction["down"] + self.block2.transaction["up"], pk_1_up)
        self.assertEqual(self.block1.transaction["up"] + self.block2.transaction["down"], pk_1_down)
        self.assertEqual(2, pk_1_neigh)
        # One link
        self.assertEqual(self.block3.transaction["up"], pk_f_up)
        self.assertEqual(self.block3.transaction["down"], pk_f_down)
        self.assertEqual(1, pk_f_neigh)
        # No links
        self.assertEqual(0, fake_up)
        self.assertEqual(0, fake_down)
        self.assertEqual(0, fake_neigh)

    @blocking_call_on_reactor_thread
    def test_neighbors(self):
        """
        The database should return the correct list of neighbors and the traffic to and from them.
        """
        extra_block = TriblerTestBlock(transaction={"up": 0, "down": 0})

        # 00 -> 11, 11 -> 22, 22 -> 33, 33 -> 44
        self.block1.public_key = unhexlify("00")
        self.block1.link_public_key = unhexlify("11")
        self.block2.public_key = unhexlify("11")
        self.block2.link_public_key = unhexlify("22")
        self.block3.public_key = unhexlify("22")
        self.block3.link_public_key = unhexlify("33")
        extra_block.public_key = unhexlify("33")
        extra_block.link_public_key = unhexlify("44")

        # Add all blocks
        self.db.add_block(self.block1)
        self.db.add_block(self.block2)
        self.db.add_block(self.block3)
        self.db.add_block(extra_block)

        expected_result = [
            ["11", "22", 46, 12, 59, 54],
            ["00", "11", 42, 13, 42, 13],
            ["22", "33", 11, 23, 23, 69]
        ]

        def verify_result(result):
            actual_result = [[str(row[0]), str(row[1]), row[2], row[3], row[4], row[5]]
                             for row in result]
            self.assertItemsEqual(expected_result, actual_result)

        d = self.db.get_graph_edges("11", neighbor_level=2)
        d.addCallback(verify_result)
        return d

    @blocking_call_on_reactor_thread
    def test_database_upgrade(self):
        """
        Set the database version to a newer version before upgrading.
        """
        self.set_db_version(1, 0)
        database_version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        aggregate_version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'aggregate_version' LIMIT 1"))
        self.assertEqual(database_version, u"4")
        self.assertEqual(aggregate_version, u"1")

    @blocking_call_on_reactor_thread
    def test_database_no_downgrade(self):
        """
        Set the database version to a newer version before upgrading.
        """
        self.set_db_version(100, 101)
        database_version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'database_version' LIMIT 1"))
        aggregate_version, = next(self.db.execute(u"SELECT value FROM option WHERE key = 'aggregate_version' LIMIT 1"))
        self.assertEqual(database_version, u"100")
        self.assertEqual(aggregate_version, u"101")

    def test_check_statistics_database_upgrade(self):
        """
        Aggregates database should be upgraded when a version number is not the latest
        """
        db_result = MockObject()
        db_result.fetchone = lambda: (str(LATEST_TRIBLERCHAIN_AGGREGATES_VERSION - 1),)
        self.db.execute = lambda _: db_result
        self.db.x = True
        self.called = False

        def verify_executescript_called(_):
            self.called = True

        self.db.executescript = verify_executescript_called
        self.db.commit = lambda: None

        self.db.check_statistics_database()

        self.assertTrue(self.called)

    def test_check_statistics_database_no_upgrade(self):
        """
        Aggregates database should be upgraded when a version number is not the latest
        """
        db_result = MockObject()
        db_result.fetchone = lambda: (str(LATEST_TRIBLERCHAIN_AGGREGATES_VERSION),)
        self.db.execute = lambda _: db_result
        self.db.x = True
        self.called = False

        def verify_executescript_called(_):
            self.called = True

        self.db.executescript = verify_executescript_called
        self.db.commit = lambda: None

        self.db.check_statistics_database()

        self.assertFalse(self.called)
