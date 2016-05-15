import unittest

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import Order, OrderId, OrderNumber, TickWasNotReserved, LogicException, \
    TickWasNotReserved


class OrderTestSuite(unittest.TestCase):
    """Order test cases."""

    def setUp(self):
        # Object creation
        self.tick = Tick(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                         OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(5),
                         Timeout(float("inf")), Timestamp(float("inf")), True)
        self.tick2 = Tick(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                          OrderId(TraderId('trader_id'), OrderNumber("order_number")), Price(100), Quantity(100),
                          Timeout(float("inf")), Timestamp(float("inf")), True)
        self.order = Order(OrderId(TraderId("trader_id"), OrderNumber("order_number")), Price(100), Quantity(30),
                           Timeout(0.0), Timestamp(10.0), False)
        self.order2 = Order(OrderId(TraderId("trader_id"), OrderNumber("order_number")), Price(100), Quantity(30),
                           Timeout(0.0), Timestamp(10.0), True)

    def test_properties(self):
        # Test for properties
        self.assertEquals(OrderId(TraderId("trader_id"), OrderNumber("order_number")), self.order.order_id)
        self.assertEquals(Price(100), self.order.price)
        self.assertEquals(Quantity(30), self.order.total_quantity)
        self.assertEquals(Quantity(30), self.order.available_quantity)
        self.assertEquals(Timestamp(10.0), self.order.timestamp)
        self.assertEquals(0.0, float(self.order.timeout))
        self.assertEquals(Quantity(0), self.order.reserved_quantity)

    def test_is_ask(self):
        # Test for is ask
        self.assertTrue(self.order2.is_ask())
        self.assertFalse(self.order.is_ask())

    def test_reserve_quantity_insufficient(self):
        # Test for reserve insufficient quantity
        self.assertFalse(self.order.reserve_quantity_for_tick(self.tick2))

    def test_reserve_quantity(self):
        # Test for reserve quantity
        self.assertEquals(Quantity(0), self.order.reserved_quantity)
        self.assertTrue(self.order.reserve_quantity_for_tick(self.tick))
        self.assertEquals(Quantity(5), self.order.reserved_quantity)

    def test_release_quantity(self):
        # Test for release quantity
        self.order.reserve_quantity_for_tick(self.tick)
        self.assertEquals(Quantity(5), self.order.reserved_quantity)
        self.order.release_quantity_for_tick(self.tick)
        self.assertEquals(Quantity(0), self.order.reserved_quantity)

    def test_release_unreserved_quantity(self):
        # Test for release unreserved quantity
        with self.assertRaises(TickWasNotReserved):
            self.order.release_quantity_for_tick(self.tick)

    def test_release_updated_quantity(self):
        # Test for release updated quantity
        self.order.reserve_quantity_for_tick(self.tick)
        self.tick.quantity = Quantity(100)
        with self.assertRaises(LogicException):
            self.order.release_quantity_for_tick(self.tick)


class OrderIDTestSuite(unittest.TestCase):
    """Order ID test cases."""

    def setUp(self):
        # Object creation
        self.order_id = OrderId(TraderId("trader_id"), OrderNumber("order_number"))
        self.order_id2 = OrderId(TraderId("trader_id"), OrderNumber("order_number"))
        self.order_id3 = OrderId(TraderId("trader_id2"), OrderNumber("order_number2"))

    def test_equality(self):
        # Test for equality
        self.assertEquals(self.order_id, self.order_id)
        self.assertEquals(self.order_id, self.order_id2)
        self.assertFalse(self.order_id == self.order_id3)
        self.assertEquals(NotImplemented, self.order_id.__eq__(""))

    def test_non_equality(self):
        # Test for non equality
        self.assertNotEquals(self.order_id, self.order_id3)

    def test_properties(self):
        # Test for properties
        self.assertEquals(OrderNumber("order_number"), self.order_id.order_number)
        self.assertEquals(TraderId("trader_id"), self.order_id.trader_id)

    def test_hashes(self):
        # Test for hashes
        self.assertEquals(self.order_id.__hash__(), self.order_id2.__hash__())
        self.assertNotEqual(self.order_id.__hash__(), self.order_id3.__hash__())

    def test_str(self):
        # Test for string representation
        self.assertEquals('trader_id.order_number', str(self.order_id))


class OrderNumberTestSuite(unittest.TestCase):
    """Order number test cases."""

    def setUp(self):
        # Object creation
        self.order_number = OrderNumber("order_number")
        self.order_number2 = OrderNumber("order_number")
        self.order_number3 = OrderNumber("order_number3")

    def test_equality(self):
        # Test for equality
        self.assertEquals(self.order_number, self.order_number)
        self.assertEquals(self.order_number, self.order_number2)
        self.assertFalse(self.order_number == self.order_number3)
        self.assertEquals(NotImplemented, self.order_number.__eq__(""))

    def test_non_equality(self):
        # Test for non equality
        self.assertNotEquals(self.order_number, self.order_number3)

    def test_hashes(self):
        # Test for hashes
        self.assertEquals(self.order_number.__hash__(), self.order_number2.__hash__())
        self.assertNotEqual(self.order_number.__hash__(), self.order_number3.__hash__())

    def test_str(self):
        # Test for string representation
        self.assertEquals('order_number', str(self.order_number))


if __name__ == '__main__':
    unittest.main()
