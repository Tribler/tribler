import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, CounterTrade


class TradeTestSuite(unittest.TestCase):
    """Trade test cases."""

    def setUp(self):
        # Object creation
        self.trade = Trade(MessageId(TraderId('0'), MessageNumber('message_number')),
                           OrderId(TraderId('0'), OrderNumber(3)),
                           OrderId(TraderId('0'), OrderNumber(4)), 1234, Timestamp(1462224447.117))

    def test_to_network(self):
        # Test for to network
        self.assertEquals(NotImplemented, self.trade.to_network())


class ProposedTradeTestSuite(unittest.TestCase):
    """Proposed trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber(1)),
                                            OrderId(TraderId('1'), OrderNumber(2)),
                                            Price(63400, 'BTC'), Quantity(30, 'MC'),
                                            Timestamp(1462224447.117))

    def test_to_network(self):
        # Test for to network
        self.assertEquals((TraderId('1'), (TraderId('0'), MessageNumber('message_number'),
                                           OrderNumber(1), TraderId('1'),
                                           OrderNumber(2), self.proposed_trade.proposal_id,
                                           Price(63400, 'BTC'), Quantity(30, 'MC'),
                                           Timestamp(1462224447.117))), self.proposed_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = ProposedTrade.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                                   "message_number": MessageNumber('message_number'),
                                                                   "order_number": OrderNumber(1),
                                                                   "recipient_trader_id": TraderId('1'),
                                                                   "recipient_order_number": OrderNumber(2),
                                                                   "proposal_id": 1234,
                                                                   "timestamp": Timestamp(1462224447.117),
                                                                   "price": Price(63400, 'BTC'),
                                                                   "quantity": Quantity(30, 'MC')}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('0'), OrderNumber(1)), data.order_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEquals(1234, data.proposal_id)
        self.assertEquals(Price(63400, 'BTC'), data.price)
        self.assertEquals(Quantity(30, 'MC'), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class DeclinedTradeTestSuite(unittest.TestCase):
    """Declined trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber(1)),
                                            OrderId(TraderId('1'), OrderNumber(2)),
                                            Price(63400, 'BTC'), Quantity(30, 'MC'), Timestamp(1462224447.117))
        self.declined_trade = Trade.decline(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            Timestamp(1462224447.117), self.proposed_trade)

    def test_to_network(self):
        # Test for to network
        data = self.declined_trade.to_network()

        self.assertEquals(data[0], TraderId("0"))
        self.assertEquals(data[1][0], TraderId("1"))
        self.assertEquals(data[1][1], MessageNumber("message_number"))
        self.assertEquals(data[1][2], OrderNumber(2))
        self.assertEquals(data[1][3], TraderId("0"))
        self.assertEquals(data[1][4], OrderNumber(1))
        self.assertEquals(data[1][5], self.proposed_trade.proposal_id)
        self.assertEquals(data[1][6], Timestamp(1462224447.117))

    def test_from_network(self):
        # Test for from network
        data = DeclinedTrade.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                                   "message_number": MessageNumber('message_number'),
                                                                   "order_number": OrderNumber(1),
                                                                   "recipient_trader_id": TraderId('1'),
                                                                   "recipient_order_number": OrderNumber(2),
                                                                   "proposal_id": 1235,
                                                                   "timestamp": Timestamp(1462224447.117),}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEquals(1235, data.proposal_id)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class CounterTradeTestSuite(unittest.TestCase):
    """Counter trade test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber(1)),
                                            OrderId(TraderId('1'), OrderNumber(2)),
                                            Price(63400, 'BTC'), Quantity(30, 'MC'),
                                            Timestamp(1462224447.117))
        self.counter_trade = Trade.counter(MessageId(TraderId('0'), MessageNumber('message_number')),
                                           Quantity(15, 'MC'), Timestamp(1462224447.117), self.proposed_trade)

    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            (TraderId('0'), (TraderId('1'), MessageNumber('message_number'), OrderNumber(2),
                             TraderId('0'), OrderNumber(1), self.proposed_trade.proposal_id,
                             Price(63400, 'BTC'), Quantity(15, 'MC'),
                             Timestamp(1462224447.117))), self.counter_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = CounterTrade.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                                  "message_number": MessageNumber('message_number'),
                                                                  "order_number": OrderNumber(1),
                                                                  "recipient_trader_id": TraderId('1'),
                                                                  "recipient_order_number": OrderNumber(2),
                                                                  "proposal_id": 1236,
                                                                  "timestamp": Timestamp(1462224447.117),
                                                                  "price": Price(63400, 'BTC'),
                                                                  "quantity": Quantity(15, 'MC'),}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('0'), OrderNumber(1)), data.order_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber(2)),
                          data.recipient_order_id)
        self.assertEquals(1236, data.proposal_id)
        self.assertEquals(Price(63400, 'BTC'), data.price)
        self.assertEquals(Quantity(15, 'MC'), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)
