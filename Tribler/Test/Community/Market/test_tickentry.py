from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.price import Price
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.tickentry import TickEntry
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class TickEntryTestSuite(AbstractServer):
    """TickEntry test cases."""

    @inlineCallbacks
    def setUp(self):
        yield super(TickEntryTestSuite, self).setUp()

        # Object creation
        tick = Tick(OrderId(TraderId('0'), OrderNumber(1)), AssetPair(AssetAmount(60, 'BTC'), AssetAmount(30, 'MB')),
                    Timeout(0), Timestamp(0.0), True)
        tick2 = Tick(OrderId(TraderId('0'), OrderNumber(2)),
                     AssetPair(AssetAmount(63400, 'BTC'), AssetAmount(30, 'MB')), Timeout(100), Timestamp.now(), True)

        self.price_level = PriceLevel(Price(100, 'MB', 'BTC'))
        self.tick_entry = TickEntry(tick, self.price_level)
        self.tick_entry2 = TickEntry(tick2, self.price_level)

    @inlineCallbacks
    def tearDown(self):
        self.tick_entry.shutdown_task_manager()
        self.tick_entry2.shutdown_task_manager()
        yield super(TickEntryTestSuite, self).tearDown()

    def test_price_level(self):
        self.assertEquals(self.price_level, self.tick_entry.price_level())

    def test_next_tick(self):
        # Test for next tick
        self.assertEquals(None, self.tick_entry.next_tick)
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEquals(self.tick_entry2, self.tick_entry.next_tick)

    def test_prev_tick(self):
        # Test for previous tick
        self.assertEquals(None, self.tick_entry.prev_tick)
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.assertEquals(self.tick_entry, self.tick_entry2.prev_tick)

    def test_str(self):
        # Test for tick string representation
        self.assertEquals('60 BTC\t@\t0.5 MB (R: 0)', str(self.tick_entry))

    def test_is_valid(self):
        # Test for is valid
        self.assertFalse(self.tick_entry.is_valid())
        self.assertTrue(self.tick_entry2.is_valid())

    def test_block_for_matching(self):
        """
        Test blocking of a match
        """
        self.tick_entry.block_for_matching(OrderId(TraderId("abc"), OrderNumber(3)))
        self.assertEqual(len(self.tick_entry._blocked_for_matching), 1)

        # Try to add it again - should be ignored
        self.tick_entry.block_for_matching(OrderId(TraderId("abc"), OrderNumber(3)))
        self.assertEqual(len(self.tick_entry._blocked_for_matching), 1)
