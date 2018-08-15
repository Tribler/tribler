import unittest

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.order_manager import OrderManager
from Tribler.community.market.core.order_repository import MemoryOrderRepository
from Tribler.community.market.core.timeout import Timeout


class PortfolioTestSuite(unittest.TestCase):
    """OrderManager test cases."""

    def setUp(self):
        # Object creation
        self.order_manager = OrderManager(MemoryOrderRepository("0"))

    def test_create_ask_order(self):
        # Test for create ask order
        ask_order = self.order_manager.create_ask_order(
            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), Timeout(0))
        self.assertTrue(ask_order.is_ask())
        self.assertEquals(OrderId(TraderId("0"), OrderNumber(1)), ask_order.order_id)
        self.assertEquals(AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), ask_order.assets)
        self.assertEquals(100, ask_order.total_quantity)
        self.assertEquals(0, int(ask_order.timeout))

    def test_create_bid_order(self):
        # Test for create bid order
        bid_order = self.order_manager.create_bid_order(
            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), Timeout(0))
        self.assertFalse(bid_order.is_ask())
        self.assertEquals(OrderId(TraderId("0"), OrderNumber(1)), bid_order.order_id)
        self.assertEquals(AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), bid_order.assets)
        self.assertEquals(100, bid_order.total_quantity)
        self.assertEquals(0, int(bid_order.timeout))

    def test_cancel_order(self):
        # test for cancel order
        order = self.order_manager.create_ask_order(
            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(10, 'MC')), Timeout(0))
        self.order_manager.cancel_order(order.order_id)
