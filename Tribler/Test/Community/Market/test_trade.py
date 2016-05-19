import unittest


from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, AcceptedTrade


class TradeTestSuite(unittest.TestCase):
    """Trade test cases."""

    def setUp(self):
        # Object creation
        self.trade = Trade(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                           OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                           OrderId(TraderId('trader_id'), OrderNumber('order_number')), Timestamp(1462224447.117),
                           False)
        self.proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                                            OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                                            Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.quick_trade = Trade.quick_propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                               OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                                               OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                                               Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                           Timestamp(1462224447.117), self.proposed_trade)
        self.declined_trade = Trade.decline(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            Timestamp(1462224447.117), self.proposed_trade)

    def test_is_quick(self):
        # Test for is quick
        self.assertFalse(self.proposed_trade.is_quick())
        self.assertTrue(self.quick_trade.is_quick())
        self.assertFalse(self.accepted_trade.is_quick())
        self.assertFalse(self.declined_trade.is_quick())

    def test_to_network(self):
        # Test for to network
        self.assertEquals(NotImplemented, self.trade.to_network())


class ProposedTradeTestSuite(unittest.TestCase):
    """Proposed trade test cases."""
	
    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                                            OrderId(TraderId('recipient_trader_id'),
                                                    OrderNumber('recipient_order_number')), Price(63400), Quantity(30),
                                            Timestamp(1462224447.117))

    def test_to_network(self):
        # Test for to network
        self.assertEquals((('recipient_trader_id',), ('trader_id', 'message_number', 'order_number',
                                                      'recipient_trader_id', 'recipient_order_number', 63400, 30,
                                                      1462224447.117, False)),
                          self.proposed_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = ProposedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "order_number": 'order_number',
                                                                   "recipient_trader_id": 'recipient_trader_id',
                                                                   "recipient_order_number": 'recipient_order_number',
                                                                   "price": 63400, "quantity": 30,
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('trader_id'), OrderNumber('order_number')), data.order_id)
        self.assertEquals(OrderId(TraderId('recipient_trader_id'), OrderNumber('recipient_order_number')),
                          data.recipient_order_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class AcceptedTradeTestSuite(unittest.TestCase):
    """Accepted trade test cases."""
	
    def setUp(self):
        # Object creation
        proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                       OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                                       OrderId(TraderId('recipient_trader_id'), OrderNumber('recipient_order_number')),
                                       Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                           Timestamp(1462224447.117), proposed_trade)
	
    def test_accepted_trade(self):
        # Test for properties
        self.assertEquals(self.accepted_trade.price, Price(63400))
        self.assertEquals(self.accepted_trade.quantity, Quantity(30))
	
    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            ((), ('trader_id', 'message_number', 'order_number', 'recipient_trader_id', 'recipient_order_number', 63400,
                  30, 1462224447.117, False)),
            self.accepted_trade.to_network())
	
    def test_from_network(self):
        # Test for from network
        data = AcceptedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "order_number": 'order_number',
                                                                   "recipient_trader_id": 'recipient_trader_id',
                                                                   "recipient_order_number": 'recipient_order_number',
                                                                   "price": 63400, "quantity": 30,
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('trader_id'), OrderNumber('order_number')), data.order_id)
        self.assertEquals(OrderId(TraderId('recipient_trader_id'), OrderNumber('recipient_order_number')),
                          data.recipient_order_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class DeclinedTradeTestSuite(unittest.TestCase):
    """Declined trade test cases."""
	
    def setUp(self):
        # Object creation
        proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                       OrderId(TraderId('trader_id'), OrderNumber('order_number')),
                                       OrderId(TraderId('recipient_trader_id'), OrderNumber('recipient_order_number')),
                                       Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.declined_trade = Trade.decline(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            Timestamp(1462224447.117), proposed_trade)
	
    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            (('recipient_trader_id',), ('trader_id', 'message_number', 'order_number', 'recipient_trader_id',
                              'recipient_order_number', 1462224447.117, False)),
            self.declined_trade.to_network())
	
    def test_from_network(self):
        # Test for from network
        data = DeclinedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "order_number": 'order_number',
                                                                   "recipient_trader_id": 'recipient_trader_id',
                                                                   "recipient_order_number": 'recipient_order_number',
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(OrderId(TraderId('recipient_trader_id'), OrderNumber('recipient_order_number')),
                          data.recipient_order_id)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


if __name__ == '__main__':
    unittest.main()
