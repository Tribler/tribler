import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, AcceptedTrade, CounterTrade


class TradeTestSuite(unittest.TestCase):
    """Trade test cases."""

    def setUp(self):
        # Object creation
        self.trade = Trade(MessageId(TraderId('0'), MessageNumber('message_number')),
                           OrderId(TraderId('0'), OrderNumber('order_number')),
                           OrderId(TraderId('0'), OrderNumber('order_number')), Timestamp(1462224447.117))
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber('order_number')),
                                            OrderId(TraderId('0'), OrderNumber('order_number')),
                                            Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('0'), MessageNumber('message_number')),
                                           Timestamp(1462224447.117), self.proposed_trade)
        self.declined_trade = Trade.decline(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            Timestamp(1462224447.117), self.proposed_trade)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(NotImplemented, self.trade.to_network())


class ProposedTradeTestSuite(unittest.TestCase):
    """Proposed trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber('order_number')),
                                            OrderId(TraderId('1'),
                                                    OrderNumber('recipient_order_number')), Price(63400), Quantity(30),
                                            Timestamp(1462224447.117))

    def test_to_network(self):
        # Test for to network
        self.assertEquals(((TraderId('1'),), (TraderId('0'), MessageNumber('message_number'),
                                              OrderNumber('order_number'), TraderId('1'),
                                              OrderNumber('recipient_order_number'), Price(63400), Quantity(30),
                                              Timestamp(1462224447.117))), self.proposed_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = ProposedTrade.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                                   "message_number": MessageNumber('message_number'),
                                                                   "order_number": OrderNumber('order_number'),
                                                                   "recipient_trader_id": TraderId('1'),
                                                                   "recipient_order_number": OrderNumber(
                                                                       'recipient_order_number'),
                                                                   "timestamp": Timestamp(1462224447.117),
                                                                   "price": Price(63400),
                                                                   "quantity": Quantity(30),}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('0'), OrderNumber('order_number')), data.order_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber('recipient_order_number')),
                          data.recipient_order_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class AcceptedTradeTestSuite(unittest.TestCase):
    """Accepted trade test cases."""

    def setUp(self):
        # Object creation
        proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                       OrderId(TraderId('0'), OrderNumber('order_number')),
                                       OrderId(TraderId('1'), OrderNumber('recipient_order_number')),
                                       Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('0'), MessageNumber('message_number')),
                                           Timestamp(1462224447.117), proposed_trade)

    def test_accepted_trade(self):
        # Test for properties
        self.assertEquals(self.accepted_trade.price, Price(63400))
        self.assertEquals(self.accepted_trade.quantity, Quantity(30))

    def test_to_network(self):
        # Test for to network
        data = self.accepted_trade.to_network()

        self.assertEquals(data[0][0], TraderId("0"))
        self.assertEquals(data[1][0], TraderId("1"))
        self.assertEquals(data[1][1], MessageNumber("message_number"))
        self.assertEquals(data[1][2], OrderNumber("recipient_order_number"))
        self.assertEquals(data[1][3], TraderId("0"))
        self.assertEquals(data[1][4], OrderNumber("order_number"))
        self.assertEquals(data[1][5], Price(63400))
        self.assertEquals(data[1][6], Quantity(30))
        self.assertEquals(data[1][7], Timestamp(1462224447.117))

    def test_from_network(self):
        # Test for from network
        data = AcceptedTrade.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                                   "message_number": MessageNumber('message_number'),
                                                                   "order_number": OrderNumber('order_number'),
                                                                   "recipient_trader_id": TraderId('1'),
                                                                   "recipient_order_number": OrderNumber(
                                                                       'recipient_order_number'),
                                                                   "timestamp": Timestamp(1462224447.117),
                                                                   "price": Price(63400),
                                                                   "quantity": Quantity(30),}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('0'), OrderNumber('order_number')), data.order_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber('recipient_order_number')),
                          data.recipient_order_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class DeclinedTradeTestSuite(unittest.TestCase):
    """Declined trade test cases."""

    def setUp(self):
        # Object creation
        proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                       OrderId(TraderId('0'), OrderNumber('order_number')),
                                       OrderId(TraderId('1'), OrderNumber('recipient_order_number')),
                                       Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.declined_trade = Trade.decline(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            Timestamp(1462224447.117), proposed_trade)

    def test_to_network(self):
        # Test for to network
        data = self.declined_trade.to_network()

        self.assertEquals(data[0][0], TraderId("0"))
        self.assertEquals(data[1][0], TraderId("1"))
        self.assertEquals(data[1][1], MessageNumber("message_number"))
        self.assertEquals(data[1][2], OrderNumber("recipient_order_number"))
        self.assertEquals(data[1][3], TraderId("0"))
        self.assertEquals(data[1][4], OrderNumber("order_number"))
        self.assertEquals(data[1][5], Timestamp(1462224447.117))

    def test_from_network(self):
        # Test for from network
        data = DeclinedTrade.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                                   "message_number": MessageNumber('message_number'),
                                                                   "order_number": OrderNumber('order_number'),
                                                                   "recipient_trader_id": TraderId('1'),
                                                                   "recipient_order_number": OrderNumber(
                                                                       'recipient_order_number'),
                                                                   "timestamp": Timestamp(1462224447.117),}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber('recipient_order_number')),
                          data.recipient_order_id)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class CounterTradeTestSuite(unittest.TestCase):
    """Counter trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber('order_number')),
                                            OrderId(TraderId('1'),
                                                    OrderNumber('recipient_order_number')), Price(63400), Quantity(30),
                                            Timestamp(1462224447.117))
        self.counter_trade = Trade.counter(MessageId(TraderId('0'), MessageNumber('message_number')),
                                           Quantity(15), Timestamp(1462224447.117), self.proposed_trade)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            ((TraderId('0'),), (TraderId('1'), MessageNumber('message_number'), OrderNumber('recipient_order_number'),
                                TraderId('0'), OrderNumber('order_number'), Price(63400), Quantity(15),
                                Timestamp(1462224447.117))), self.counter_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = CounterTrade.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                                  "message_number": MessageNumber('message_number'),
                                                                  "order_number": OrderNumber('order_number'),
                                                                  "recipient_trader_id": TraderId('1'),
                                                                  "recipient_order_number": OrderNumber(
                                                                      'recipient_order_number'),
                                                                  "timestamp": Timestamp(1462224447.117),
                                                                  "price": Price(63400),
                                                                  "quantity": Quantity(15),}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('0'), OrderNumber('order_number')), data.order_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber('recipient_order_number')),
                          data.recipient_order_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(15), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


if __name__ == '__main__':
    unittest.main()
