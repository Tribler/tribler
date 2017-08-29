import unittest

import time

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber, TickWasNotReserved
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction


class OrderTestSuite(unittest.TestCase):
    """Order test cases."""

    def setUp(self):
        # Object creation
        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber(1))
        self.transaction = Transaction(self.transaction_id, Price(100, 'BTC'), Quantity(30, 'MC'),
                                       OrderId(TraderId('0'), OrderNumber(2)),
                                       OrderId(TraderId('1'), OrderNumber(1)), Timestamp(0.0))
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('1')),
                                            OrderId(TraderId('0'), OrderNumber(2)),
                                            OrderId(TraderId('1'), OrderNumber(3)),
                                            Price(100, 'BTC'), Quantity(30, 'MC'), Timestamp(0.0))

        self.tick = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                         OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'), Quantity(5, 'MC'),
                         Timeout(0.0), Timestamp(float("inf")), True)
        self.tick2 = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                          OrderId(TraderId('0'), OrderNumber(2)), Price(100, 'BTC'), Quantity(100, 'MC'),
                          Timeout(0.0), Timestamp(float("inf")), True)

        self.order_timestamp = Timestamp.now()
        self.order = Order(OrderId(TraderId("0"), OrderNumber(3)), Price(100, 'BTC'), Quantity(30, 'MC'),
                           Timeout(5000), self.order_timestamp, False)
        self.order2 = Order(OrderId(TraderId("0"), OrderNumber(4)), Price(100, 'BTC'), Quantity(30, 'MC'),
                            Timeout(5), Timestamp(time.time() - 1000), True)

    def test_add_trade(self):
        """
        Test the add trade method of an order
        """
        self.order.reserve_quantity_for_tick(OrderId(TraderId('5'), OrderNumber(1)), Quantity(10, 'MC'))
        self.assertEquals(self.order.traded_quantity, Quantity(0, 'MC'))
        self.order.add_trade(OrderId(TraderId('5'), OrderNumber(1)), Quantity(10, 'MC'))
        self.assertEquals(self.order.traded_quantity, Quantity(10, 'MC'))

        self.order.reserve_quantity_for_tick(OrderId(TraderId('6'), OrderNumber(1)), Quantity(20, 'MC'))
        self.order.add_trade(OrderId(TraderId('6'), OrderNumber(1)), Quantity(20, 'MC'))
        self.assertTrue(self.order.is_complete())
        self.assertFalse(self.order.cancelled)

    def test_is_ask(self):
        # Test for is ask
        self.assertTrue(self.order2.is_ask())
        self.assertFalse(self.order.is_ask())

    def test_reserve_quantity_insufficient(self):
        # Test for reserve insufficient quantity
        self.assertRaises(ValueError, self.order.reserve_quantity_for_tick, self.tick2.order_id, self.tick2.quantity)

    def test_reserve_quantity(self):
        # Test for reserve quantity
        self.assertEquals(Quantity(0, 'MC'), self.order.reserved_quantity)
        self.order.reserve_quantity_for_tick(self.tick.order_id, self.tick.quantity)
        self.assertEquals(Quantity(5, 'MC'), self.order.reserved_quantity)
        self.order.reserve_quantity_for_tick(self.tick.order_id, self.tick.quantity)
        self.assertEquals(Quantity(10, 'MC'), self.order.reserved_quantity)

    def test_release_quantity(self):
        # Test for release quantity
        self.order.reserve_quantity_for_tick(self.tick.order_id, self.tick.quantity)
        self.assertEquals(Quantity(5, 'MC'), self.order.reserved_quantity)
        self.order.release_quantity_for_tick(self.tick.order_id, Quantity(5, 'MC'))
        self.assertEquals(Quantity(0, 'MC'), self.order.reserved_quantity)

        self.order.reserve_quantity_for_tick(self.tick.order_id, self.tick.quantity)
        quantity = self.tick.quantity + Quantity(1, self.tick.quantity.wallet_id)
        self.assertRaises(ValueError, self.order.release_quantity_for_tick, self.tick.order_id, quantity)

    def test_release_unreserved_quantity(self):
        # Test for release unreserved quantity
        with self.assertRaises(TickWasNotReserved):
            self.order.release_quantity_for_tick(self.tick.order_id, Quantity(5, 'MC'))

    def test_is_valid(self):
        self.assertTrue(self.order.is_valid())
        self.assertFalse(self.order2.is_valid())

    def test_status(self):
        """
        Test the status of an order
        """
        self.assertEqual(self.order.status, "open")
        self.order._timeout = Timeout(0)
        self.assertEqual(self.order.status, "expired")
        self.order._traded_quantity = self.order.total_quantity
        self.assertEqual(self.order.status, "completed")
        self.order._cancelled = True
        self.assertEqual(self.order.status, "cancelled")

    def test_to_dict(self):
        """
        Test the conversion of an order to a dictionary
        """
        self.assertEqual(self.order.to_dictionary(), {
            "trader_id": "0",
            "cancelled": False,
            "completed_timestamp": None,
            "is_ask": False,
            "order_number": 3,
            "price": 100.0,
            "price_type": "BTC",
            "quantity": 30.0,
            "quantity_type": "MC",
            "reserved_quantity": 0.0,
            "traded_quantity": 0.0,
            "status": "open",
            "timeout": 5000.0,
            "timestamp": float(self.order_timestamp)
        })


class OrderIDTestSuite(unittest.TestCase):
    """Order ID test cases."""

    def setUp(self):
        # Object creation
        self.order_id = OrderId(TraderId("0"), OrderNumber(1))
        self.order_id2 = OrderId(TraderId("0"), OrderNumber(1))
        self.order_id3 = OrderId(TraderId("0"), OrderNumber(2))

    def test_equality(self):
        # Test for equality
        self.assertEquals(self.order_id, self.order_id)
        self.assertEquals(self.order_id, self.order_id2)
        self.assertFalse(self.order_id == self.order_id3)
        self.assertEquals(NotImplemented, self.order_id.__eq__(""))

    def test_non_equality(self):
        # Test for non equality
        self.assertNotEquals(self.order_id, self.order_id3)

    def test_hashes(self):
        # Test for hashes
        self.assertEquals(self.order_id.__hash__(), self.order_id2.__hash__())
        self.assertNotEqual(self.order_id.__hash__(), self.order_id3.__hash__())

    def test_str(self):
        # Test for string representation
        self.assertEquals('0.1', str(self.order_id))


class OrderNumberTestSuite(unittest.TestCase):
    """Order number test cases."""

    def setUp(self):
        # Object creation
        self.order_number = OrderNumber(1)
        self.order_number2 = OrderNumber(1)
        self.order_number3 = OrderNumber(3)

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            OrderNumber(1.0)

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
        self.assertEquals('1', str(self.order_number))

    def test_int(self):
        # Test for integer representation
        self.assertEquals(1, int(self.order_number))
