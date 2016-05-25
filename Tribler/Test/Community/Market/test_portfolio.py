import unittest

from Tribler.community.market.core.order_manager import OrderManager
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.order_repository import MemoryOrderRepository


class PortfolioTestSuite(unittest.TestCase):
    """OrderManager test cases."""

    def setUp(self):
        # Object creation
        self.order_manager = OrderManager(MemoryOrderRepository("0"))

    def test_create_ask_order(self):
        # Test for create ask order
        ask_order = self.order_manager.create_ask_order(Price(100), Quantity(10), Timeout(0.0))
        self.assertTrue(ask_order.is_ask())
        self.assertEquals(OrderId(TraderId("0"), OrderNumber("1")), ask_order.order_id)
        self.assertEquals(Price(100), ask_order.price)
        self.assertEquals(Quantity(10), ask_order.total_quantity)
        self.assertEquals(0.0, float(ask_order.timeout))

    def test_create_bid_order(self):
        # Test for create bid order
        bid_order = self.order_manager.create_bid_order(Price(100), Quantity(10), Timeout(0.0))
        self.assertFalse(bid_order.is_ask())
        self.assertEquals(OrderId(TraderId("0"), OrderNumber("1")), bid_order.order_id)
        self.assertEquals(Price(100), bid_order.price)
        self.assertEquals(Quantity(10), bid_order.total_quantity)
        self.assertEquals(0.0, float(bid_order.timeout))

    def test_cancel_order(self):
        # test for cancel order
        order = self.order_manager.create_ask_order(Price(100), Quantity(10), Timeout(0.0))
        self.order_manager.cancel_order(order.order_id)

if __name__ == '__main__':
    unittest.main()
