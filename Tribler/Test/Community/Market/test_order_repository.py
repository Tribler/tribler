import unittest

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.order_repository import MemoryOrderRepository
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class MemoryOrderRepositoryTestSuite(unittest.TestCase):
    """Memory order repository test cases."""

    def setUp(self):
        # Object creation
        self.memory_order_repository = MemoryOrderRepository("0")
        self.order_id = OrderId(TraderId("0"), OrderNumber(1))
        self.order = Order(self.order_id, AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MC')),
                           Timeout(0), Timestamp(10.0), False)
        self.order2 = Order(self.order_id, AssetPair(AssetAmount(1000, 'BTC'), AssetAmount(30, 'MC')),
                            Timeout(0), Timestamp(10.0), False)

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            self.memory_order_repository = MemoryOrderRepository("-")

    def test_add(self):
        # Test for add
        self.assertEquals([], self.memory_order_repository.find_all())
        self.memory_order_repository.add(self.order)
        self.assertEquals([self.order], (self.memory_order_repository.find_all()))

    def test_delete_by_id(self):
        # Test for delete by id
        self.memory_order_repository.add(self.order)
        self.assertEquals([self.order], self.memory_order_repository.find_all())
        self.memory_order_repository.delete_by_id(self.order_id)
        self.assertEquals([], self.memory_order_repository.find_all())

    def test_find_by_id(self):
        # Test for find by id
        self.assertEquals(None, self.memory_order_repository.find_by_id(self.order_id))
        self.memory_order_repository.add(self.order)
        self.assertEquals(self.order, self.memory_order_repository.find_by_id(self.order_id))

    def test_find_all(self):
        # Test for find all
        self.assertEquals([], self.memory_order_repository.find_all())
        self.memory_order_repository.add(self.order)
        self.assertEquals([self.order], self.memory_order_repository.find_all())

    def test_next_identity(self):
        # Test for next identity
        self.assertEquals(OrderId(TraderId("0"), OrderNumber(1)),
                          self.memory_order_repository.next_identity())

    def test_update(self):
        # Test for update
        self.memory_order_repository.add(self.order)
        self.memory_order_repository.update(self.order2)
        self.assertNotEquals(self.order, self.memory_order_repository.find_by_id(self.order_id))
        self.assertEquals(self.order2, self.memory_order_repository.find_by_id(self.order_id))
