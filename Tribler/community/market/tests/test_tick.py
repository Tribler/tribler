import time
import unittest

from Tribler.community.market.core.tick import TraderId, OrderNumber, MessageNumber, OrderId, MessageId, Price, \
    Quantity, Timeout, Timestamp, Message, Tick, Ask, Bid, Trade, ProposedTrade, AcceptedTrade, DeclinedTrade


class TickTestSuite(unittest.TestCase):
    """Tick test cases."""

    def test_trader_id(self):
        # Object creation
        trader_id = TraderId('trader_id')
        trader_id2 = TraderId('trader_id')
        trader_id3 = TraderId('trader_id_2')

        # Test for conversions
        self.assertEqual('trader_id', str(trader_id))

        # Test for equality
        self.assertTrue(trader_id == trader_id2)
        self.assertTrue(trader_id == trader_id)
        self.assertTrue(trader_id != trader_id3)
        self.assertFalse(trader_id == 6)

        # Test for hashes
        self.assertEqual(trader_id.__hash__(), trader_id2.__hash__())
        self.assertNotEqual(trader_id.__hash__(), trader_id3.__hash__())

    def test_order_number(self):
        # Object creation
        order_number = OrderNumber('order_number')
        order_number2 = OrderNumber('order_number')
        order_number3 = OrderNumber('order_number_2')

        # Test for conversions
        self.assertEqual('order_number', str(order_number))

        # Test for equality
        self.assertTrue(order_number == order_number2)
        self.assertTrue(order_number == order_number)
        self.assertTrue(order_number != order_number3)
        self.assertFalse(order_number == 6)

        # Test for hashes
        self.assertEqual(order_number.__hash__(), order_number2.__hash__())
        self.assertNotEqual(order_number.__hash__(), order_number3.__hash__())

    def test_message_number(self):
        # Object creation
        message_number = MessageNumber('message_number')
        message_number2 = MessageNumber('message_number')
        message_number3 = MessageNumber('message_number_2')

        # Test for conversions
        self.assertEqual('message_number', str(message_number))

        # Test for equality
        self.assertTrue(message_number == message_number2)
        self.assertTrue(message_number == message_number)
        self.assertTrue(message_number != message_number3)
        self.assertFalse(message_number == 6)

        # Test for hashes
        self.assertEqual(message_number.__hash__(), message_number2.__hash__())
        self.assertNotEqual(message_number.__hash__(), message_number3.__hash__())

    def test_order_id(self):
        # Object creation
        trader_id = TraderId('trader_id')
        order_number = OrderNumber('order_number')
        order_number2 = OrderNumber('order_number2')
        order_id = OrderId(trader_id, order_number)
        order_id2 = OrderId(trader_id, order_number)
        order_id3 = OrderId(trader_id, order_number2)

        # Test for properties
        self.assertEqual(trader_id, order_id.trader_id)
        self.assertEqual(order_number, order_id.order_number)

        # Test for conversions
        self.assertEqual('trader_id.order_number', str(order_id))

        # Test for equality
        self.assertTrue(order_id == order_id2)
        self.assertTrue(order_id == order_id)
        self.assertTrue(order_id != order_id3)
        self.assertFalse(order_id == 6)

        # Test for hashes
        self.assertEqual(order_id.__hash__(), order_id2.__hash__())
        self.assertNotEqual(order_id.__hash__(), order_id3.__hash__())

    def test_message_id(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_number2 = MessageNumber('message_number2')
        message_id = MessageId(trader_id, message_number)
        message_id2 = MessageId(trader_id, message_number)
        message_id3 = MessageId(trader_id, message_number2)

        # Test for properties
        self.assertEqual(trader_id, message_id.trader_id)
        self.assertEqual(message_number, message_id.message_number)

        # Test for conversions
        self.assertEqual('trader_id.message_number', str(message_id))

        # Test for equality
        self.assertTrue(message_id == message_id2)
        self.assertTrue(message_id == message_id)
        self.assertTrue(message_id != message_id3)
        self.assertFalse(message_id == 6)

        # Test for hashes
        self.assertEqual(message_id.__hash__(), message_id2.__hash__())
        self.assertNotEqual(message_id.__hash__(), message_id3.__hash__())

    def test_price(self):
        # Object creation
        price = Price(63400)
        price2 = Price.from_float(6.34)
        price3 = Price.from_mil(63400)
        price4 = Price.from_float(18.3)
        price5 = Price(0)

        # Test for init validation
        with self.assertRaises(ValueError):
            Price(-1)

        # Test for conversions
        self.assertEqual(63400, int(price))
        self.assertEqual(63400, int(price2))
        self.assertEqual('6.3400', str(price))
        self.assertEqual('6.3400', str(price2))

        # Test for addition
        self.assertEqual(Price.from_float(24.64), price2 + price4)
        self.assertFalse(price4 is (price4 + price))
        price3 += price5
        self.assertEqual(Price.from_float(6.34), price3)
        self.assertEqual(NotImplemented, price.__add__(10))

        # Test for subtraction
        self.assertEqual(Price.from_float(11.96), price4 - price2)
        self.assertFalse(price is (price - price))
        price3 -= price5
        self.assertEqual(Price.from_float(6.34), price3)
        self.assertEqual(NotImplemented, price.__sub__(10))
        with self.assertRaises(ValueError):
            price - price4

        # Test for comparison
        self.assertTrue(price2 < price4)
        self.assertTrue(price4 <= price4)
        self.assertTrue(price4 > price2)
        self.assertTrue(price4 >= price4)
        self.assertEqual(NotImplemented, price.__le__(10))
        self.assertEqual(NotImplemented, price.__lt__(10))
        self.assertEqual(NotImplemented, price.__ge__(10))
        self.assertEqual(NotImplemented, price.__gt__(10))

        # Test for equality
        self.assertTrue(price == price3)
        self.assertTrue(price == price)
        self.assertTrue(price != price4)
        self.assertFalse(price == 6)

        # Test for hashes
        self.assertEqual(price.__hash__(), price3.__hash__())
        self.assertNotEqual(price.__hash__(), price4.__hash__())

    def test_quantity(self):
        # Object creation
        quantity = Quantity(30)
        quantity2 = Quantity.from_mil(100000)
        quantity3 = Quantity.from_mil(0)
        quantity4 = Quantity.from_float(10.0)

        # Test for init validation
        with self.assertRaises(ValueError):
            Quantity(-1)

        # Test for conversions
        self.assertEqual(30, int(quantity))
        self.assertEqual(100000, int(quantity2))
        self.assertEqual('0.0030', str(quantity))
        self.assertEqual('10.0000', str(quantity2))

        # Test for addition
        self.assertEqual(Quantity.from_mil(100030), quantity + quantity2)
        self.assertFalse(quantity is (quantity + quantity3))
        quantity += quantity3
        self.assertEqual(Quantity(30), quantity)
        self.assertEqual(NotImplemented, quantity.__add__(10))

        # Test for subtraction
        self.assertEqual(Quantity(99970), quantity2 - quantity)
        self.assertFalse(quantity is (quantity - quantity3))
        quantity -= quantity3
        self.assertEqual(Quantity(30), quantity)
        self.assertEqual(NotImplemented, quantity.__sub__(10))
        with self.assertRaises(ValueError):
            quantity - quantity2

        # Test for comparison
        self.assertTrue(quantity < quantity2)
        self.assertTrue(quantity <= quantity)
        self.assertTrue(quantity2 > quantity)
        self.assertTrue(quantity2 >= quantity2)
        self.assertEqual(NotImplemented, quantity.__lt__(10))
        self.assertEqual(NotImplemented, quantity.__le__(10))
        self.assertEqual(NotImplemented, quantity.__gt__(10))
        self.assertEqual(NotImplemented, quantity.__ge__(10))

        # Test for equality
        self.assertTrue(quantity2 == quantity4)
        self.assertTrue(quantity == quantity)
        self.assertTrue(quantity != quantity2)
        self.assertFalse(quantity == 6)

        # Test for hashes
        self.assertEqual(quantity2.__hash__(), quantity4.__hash__())
        self.assertNotEqual(quantity.__hash__(), quantity2.__hash__())

    def test_timeout(self):
        # Object creation
        timeout = Timeout(1462224447.117)
        timeout2 = Timeout(1462224447.117)
        timeout3 = Timeout(1305743832.438)

        # Test for init validation
        with self.assertRaises(ValueError):
            Timeout(-1.0)

        # Test for timed out
        self.assertFalse(timeout.is_timed_out(Timestamp(1462224447.117)))
        self.assertFalse(timeout.is_timed_out(Timestamp(1262224447.117)))
        self.assertTrue(timeout.is_timed_out(Timestamp(1462224448.117)))

        # Test for conversions
        self.assertEqual(1462224447.117, float(timeout))
        self.assertEqual('2016-05-02 23:27:27.117000', str(timeout))

        # Test for hashes
        self.assertEqual(timeout.__hash__(), timeout2.__hash__())
        self.assertNotEqual(timeout.__hash__(), timeout3.__hash__())

    def test_timestamp(self):
        # Object creation
        timestamp = Timestamp(1462224447.117)
        timestamp2 = Timestamp(1462224447.117)
        timestamp3 = Timestamp(1305743832.438)

        # Test for init validation
        with self.assertRaises(ValueError):
            Timestamp(-1.0)

        # Test for now
        self.assertEqual(time.time(), float(Timestamp.now()))

        # Test for conversions
        self.assertEqual(1462224447.117, float(timestamp))
        self.assertEqual('2016-05-02 23:27:27.117000', str(timestamp))

        # Test for comparison
        self.assertTrue(timestamp3 < timestamp)
        self.assertTrue(timestamp <= timestamp)
        self.assertTrue(timestamp > timestamp3)
        self.assertTrue(timestamp3 >= timestamp3)
        self.assertTrue(timestamp3 < 1405743832.438)
        self.assertTrue(timestamp <= 1462224447.117)
        self.assertTrue(timestamp > 1362224447.117)
        self.assertTrue(timestamp3 >= 1305743832.438)
        self.assertEqual(NotImplemented, timestamp.__lt__(10))
        self.assertEqual(NotImplemented, timestamp.__le__(10))
        self.assertEqual(NotImplemented, timestamp.__gt__(10))
        self.assertEqual(NotImplemented, timestamp.__ge__(10))

        # Test for equality
        self.assertTrue(timestamp == timestamp2)
        self.assertTrue(timestamp == timestamp)
        self.assertTrue(timestamp != timestamp3)
        self.assertFalse(timestamp == 6)

        # Test for hashes
        self.assertEqual(timestamp.__hash__(), timestamp2.__hash__())
        self.assertNotEqual(timestamp.__hash__(), timestamp3.__hash__())

    def test_message(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        timestamp = Timestamp(float("inf"))
        message = Message(message_id, timestamp, True)
        message2 = Message(message_id, timestamp, False)

        # Test for properties
        self.assertEqual(message_id, message.message_id)
        self.assertEqual(timestamp, message.timestamp)

        # Test for is tick
        self.assertTrue(message.is_tick())
        self.assertFalse(message2.is_tick())

    def test_tick(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(float("inf"))
        timeout2 = Timeout(0.0)
        timestamp = Timestamp(float("inf"))
        timestamp2 = Timestamp(0.0)

        tick = Tick(message_id, price, quantity, timeout, timestamp, True)
        tick2 = Tick(message_id, price, quantity, timeout2, timestamp2, False)

        # Test for properties
        self.assertEqual(price, tick.price)
        self.assertEqual(quantity, tick.quantity)
        self.assertEqual(timeout, tick.timeout)
        self.assertEqual(timestamp, tick.timestamp)

        # Test 'is ask' function
        self.assertTrue(tick.is_ask())
        self.assertFalse(tick2.is_ask())

        # Test for is valid
        self.assertTrue(tick.is_valid())
        self.assertFalse(tick2.is_valid())

        # Test for to network
        self.assertEquals(((), ('trader_id', 'message_number', 63400, 30, float("inf"), float("inf"))),
                          tick.to_network())

    def test_ask(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)

        ask = Ask.create(message_id, price, quantity, timeout, timestamp)

        # Test for properties
        self.assertEquals(message_id, ask.message_id)
        self.assertEquals(price, ask.price)
        self.assertEquals(quantity, ask.quantity)
        self.assertEquals(float(timeout), float(ask.timeout))
        self.assertEquals(timestamp, ask.timestamp)

        # Test for from network
        data = Ask.from_network(type('Data', (object,), {"trader_id": 'trader_id', "message_number": 'message_number',
                                                         "price": 63400, "quantity": 30, "timeout": 1462224447.117,
                                                         "timestamp": 1462224447.117}))

        self.assertEquals(message_id, data.message_id)
        self.assertEquals(price, data.price)
        self.assertEquals(quantity, data.quantity)
        self.assertEquals(float(timeout), float(data.timeout))
        self.assertEquals(timestamp, data.timestamp)

    def test_bid(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timeout = Timeout(1462224447.117)
        timestamp = Timestamp(1462224447.117)

        bid = Bid.create(message_id, price, quantity, timeout, timestamp)

        # Test for properties
        self.assertEquals(message_id, bid.message_id)
        self.assertEquals(price, bid.price)
        self.assertEquals(quantity, bid.quantity)
        self.assertEquals(float(timeout), float(bid.timeout))
        self.assertEquals(timestamp, bid.timestamp)

        # Test for from network
        data = Bid.from_network(type('Data', (object,), {"trader_id": 'trader_id', "message_number": 'message_number',
                                                         "price": 63400, "quantity": 30, "timeout": 1462224447.117,
                                                         "timestamp": 1462224447.117}))

        self.assertEquals(message_id, data.message_id)
        self.assertEquals(price, data.price)
        self.assertEquals(quantity, data.quantity)
        self.assertEquals(float(timeout), float(data.timeout))
        self.assertEquals(timestamp, data.timestamp)

    def test_trade(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        sender_message_id = MessageId(trader_id, message_number)
        recipient_message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timestamp = Timestamp(1462224447.117)

        # Test for instantiation
        trade = Trade(message_id, sender_message_id, timestamp, False, False, False)
        proposed_trade = Trade.propose(message_id, sender_message_id, recipient_message_id, price, quantity, timestamp)
        quick_proposed_trade = Trade.quick_propose(message_id, sender_message_id, recipient_message_id, price, quantity,
                                                   timestamp)
        accepted_trade = Trade.accept(message_id, timestamp, proposed_trade)
        declined_trade = Trade.decline(message_id, timestamp, proposed_trade)

        # Test for is accepted
        self.assertFalse(proposed_trade.is_accepted())
        self.assertFalse(quick_proposed_trade.is_accepted())
        self.assertTrue(accepted_trade.is_accepted())
        self.assertFalse(declined_trade.is_accepted())

        # Test for is quick
        self.assertFalse(proposed_trade.is_quick())
        self.assertTrue(quick_proposed_trade.is_quick())
        self.assertFalse(accepted_trade.is_quick())
        self.assertFalse(declined_trade.is_quick())

        # Test for is proposed
        self.assertTrue(proposed_trade.is_proposed())
        self.assertTrue(quick_proposed_trade.is_proposed())
        self.assertFalse(accepted_trade.is_proposed())
        self.assertFalse(declined_trade.is_proposed())

        # Test for to network
        self.assertEquals(NotImplemented, trade.to_network())

    def test_proposed_trade(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        sender_message_id = MessageId(trader_id, message_number)
        recipient_message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timestamp = Timestamp(1462224447.117)

        proposed_trade = Trade.propose(message_id, sender_message_id, recipient_message_id, price, quantity, timestamp)

        # Test for to network
        self.assertEquals((('trader_id',), ('trader_id', 'message_number', 'trader_id', 'message_number', 'trader_id',
                                            'message_number', 63400, 30, 1462224447.117, False)),
                          proposed_trade.to_network())

        # Test for from network
        data = ProposedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "sender_trader_id": 'trader_id',
                                                                   "sender_message_number": 'message_number',
                                                                   "recipient_trader_id": 'trader_id',
                                                                   "recipient_message_number": 'message_number',
                                                                   "price": 63400, "quantity": 30,
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(message_id, data.message_id)
        self.assertEquals(recipient_message_id, data.message_id)
        self.assertEquals(sender_message_id, data.message_id)
        self.assertEquals(price, data.price)
        self.assertEquals(quantity, data.quantity)
        self.assertEquals(timestamp, data.timestamp)

    def test_accepted_trade(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        sender_message_id = MessageId(trader_id, message_number)
        recipient_message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timestamp = Timestamp(1462224447.117)
        proposed_trade = Trade.propose(message_id, sender_message_id, recipient_message_id, price, quantity, timestamp)

        accepted_trade = Trade.accept(message_id, timestamp, proposed_trade)

        # Test for properties
        self.assertEquals(accepted_trade.sender_message_id, sender_message_id)

        # Test for to network
        self.assertEquals(
            ((), ('trader_id', 'message_number', 'trader_id', 'message_number', 'trader_id', 'message_number', 63400,
                  30, 1462224447.117, False)),
            accepted_trade.to_network())

        # Test for from network
        data = AcceptedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "sender_trader_id": 'trader_id',
                                                                   "sender_message_number": 'message_number',
                                                                   "recipient_trader_id": 'trader_id',
                                                                   "recipient_message_number": 'message_number',
                                                                   "price": 63400, "quantity": 30,
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(message_id, data.message_id)
        self.assertEquals(recipient_message_id, data.message_id)
        self.assertEquals(sender_message_id, data.message_id)
        self.assertEquals(price, data.price)
        self.assertEquals(quantity, data.quantity)
        self.assertEquals(timestamp, data.timestamp)

    def test_declined_trade(self):
        # Object creation
        trader_id = TraderId('trader_id')
        message_number = MessageNumber('message_number')
        message_id = MessageId(trader_id, message_number)
        sender_message_id = MessageId(trader_id, message_number)
        recipient_message_id = MessageId(trader_id, message_number)
        price = Price(63400)
        quantity = Quantity(30)
        timestamp = Timestamp(1462224447.117)
        proposed_trade = Trade.propose(message_id, sender_message_id, recipient_message_id, price, quantity, timestamp)

        declined_trade = Trade.decline(message_id, timestamp, proposed_trade)

        # Test for to network
        self.assertEquals(
            (('trader_id',), ('trader_id', 'message_number', 'trader_id', 'message_number', 1462224447.117, False)),
            declined_trade.to_network())

        # Test for from network
        data = DeclinedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "recipient_trader_id": 'trader_id',
                                                                   "recipient_message_number": 'message_number',
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(message_id, data.message_id)
        self.assertEquals(recipient_message_id, data.message_id)
        self.assertEquals(timestamp, data.timestamp)


if __name__ == '__main__':
    unittest.main()
