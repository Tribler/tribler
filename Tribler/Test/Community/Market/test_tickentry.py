from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.assetamount import Price
from Tribler.community.market.core.pricelevel import PriceLevel
from Tribler.community.market.core.assetamount import Quantity
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.tickentry import TickEntry
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread


class TickEntryTestSuite(AbstractServer):
    """TickEntry test cases."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TickEntryTestSuite, self).setUp(annotate=annotate)

        # Object creation
        tick = Tick(OrderId(TraderId('0'), OrderNumber(1)), Price(63400, 'BTC'), Quantity(30, 'MC'),
                    Timeout(0.0), Timestamp(0.0), True)
        tick2 = Tick(OrderId(TraderId('0'), OrderNumber(2)), Price(63400, 'BTC'), Quantity(30, 'MC'),
                     Timeout(100), Timestamp.now(), True)

        self.price_level = PriceLevel('MC', Price(100, 'BTC'))
        self.tick_entry = TickEntry(tick, self.price_level)
        self.tick_entry2 = TickEntry(tick2, self.price_level)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.tick_entry.shutdown_task_manager()
        self.tick_entry2.shutdown_task_manager()
        yield super(TickEntryTestSuite, self).tearDown(annotate=annotate)

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
        self.assertEquals('30 MC\t@\t63400 BTC (R: 0 MC)', str(self.tick_entry))

    def test_is_valid(self):
        # Test for is valid
        self.assertFalse(self.tick_entry.is_valid())
        self.assertTrue(self.tick_entry2.is_valid())

    def test_quantity_setter(self):
        # Test for quantity setter
        self.price_level.append_tick(self.tick_entry)
        self.price_level.append_tick(self.tick_entry2)
        self.tick_entry.quantity = Quantity(15, 'MC')
        self.assertEquals(Quantity(15, 'MC'), self.tick_entry.quantity)

    def test_block_for_matching(self):
        """
        Test blocking of a match
        """
        self.tick_entry.block_for_matching(OrderId(TraderId("abc"), OrderNumber(3)))
        self.assertEqual(len(self.tick_entry._blocked_for_matching), 1)

        # Try to add it again - should be ignored
        self.tick_entry.block_for_matching(OrderId(TraderId("abc"), OrderNumber(3)))
        self.assertEqual(len(self.tick_entry._blocked_for_matching), 1)
