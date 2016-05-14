import unittest


from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, AcceptedTrade


class TradeTestSuite(unittest.TestCase):
    """Trade test cases."""

    def setUp(self):
        # Object creation
        self.trade = Trade(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                           MessageId(TraderId('trader_id'), MessageNumber('message_number')), Timestamp(1462224447.117),
                           False, False, False)
        self.proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.quick_trade = Trade.quick_propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                               MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                               MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                               Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                           Timestamp(1462224447.117), self.proposed_trade)
        self.declined_trade = Trade.decline(MessageId(TraderId('trader_id'), MessageNumber('message_number')),
                                            Timestamp(1462224447.117), self.proposed_trade)

    def test_is_accepted(self):
        # Test for is accepted
        self.assertFalse(self.proposed_trade.is_accepted())
        self.assertFalse(self.quick_trade.is_accepted())
        self.assertTrue(self.accepted_trade.is_accepted())
        self.assertFalse(self.declined_trade.is_accepted())

    def test_is_quick(self):
        # Test for is quick
        self.assertFalse(self.proposed_trade.is_quick())
        self.assertTrue(self.quick_trade.is_quick())
        self.assertFalse(self.accepted_trade.is_quick())
        self.assertFalse(self.declined_trade.is_quick())

    def test_is_proposed(self):
        # Test for is proposed
        self.assertTrue(self.proposed_trade.is_proposed())
        self.assertTrue(self.quick_trade.is_proposed())
        self.assertFalse(self.accepted_trade.is_proposed())
        self.assertFalse(self.declined_trade.is_proposed())

    def test_to_network(self):
        # Test for to network
        self.assertEquals(NotImplemented, self.trade.to_network())


class ProposedTradeTestSuite(unittest.TestCase):
    """Proposed trade test cases."""
	
    def setUp(self):
        # Object creation
        self.proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')), MessageId(TraderId('trader_id'), MessageNumber('message_number')), MessageId(TraderId('trader_id'), MessageNumber('message_number')), Price(63400), Quantity(30), Timestamp(1462224447.117))

    def test_to_network(self):
        # Test for to network
        self.assertEquals((('trader_id',), ('trader_id', 'message_number', 'trader_id', 'message_number', 'trader_id',
                                            'message_number', 63400, 30, 1462224447.117, False)),
                          self.proposed_trade.to_network())

    def test_from_network(self):
        # Test for from network
        data = ProposedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "sender_trader_id": 'trader_id',
                                                                   "sender_message_number": 'message_number',
                                                                   "recipient_trader_id": 'trader_id',
                                                                   "recipient_message_number": 'message_number',
                                                                   "price": 63400, "quantity": 30,
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.recipient_message_id)
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.sender_message_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class AcceptedTradeTestSuite(unittest.TestCase):
    """Accepted trade test cases."""
	
    def setUp(self):
        # Object creation
        proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')), MessageId(TraderId('trader_id'), MessageNumber('message_number')), MessageId(TraderId('trader_id'), MessageNumber('message_number')), Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.accepted_trade = Trade.accept(MessageId(TraderId('trader_id'), MessageNumber('message_number')), Timestamp(1462224447.117), proposed_trade)
	
    def test_accepted_trade(self):
        # Test for properties
        self.assertEquals(self.accepted_trade.sender_message_id, MessageId(TraderId('trader_id'), MessageNumber('message_number')))
	
    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            ((), ('trader_id', 'message_number', 'trader_id', 'message_number', 'trader_id', 'message_number', 63400,
                  30, 1462224447.117, False)),
            self.accepted_trade.to_network())
	
    def test_from_network(self):
        # Test for from network
        data = AcceptedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "sender_trader_id": 'trader_id',
                                                                   "sender_message_number": 'message_number',
                                                                   "recipient_trader_id": 'trader_id',
                                                                   "recipient_message_number": 'message_number',
                                                                   "price": 63400, "quantity": 30,
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.sender_message_id)
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.recipient_message_id)
        self.assertEquals(Price(63400), data.price)
        self.assertEquals(Quantity(30), data.quantity)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


class DeclinedTradeTestSuite(unittest.TestCase):
    """Declined trade test cases."""
	
    def setUp(self):
        # Object creation
        proposed_trade = Trade.propose(MessageId(TraderId('trader_id'), MessageNumber('message_number')), MessageId(TraderId('trader_id'), MessageNumber('message_number')), MessageId(TraderId('trader_id'), MessageNumber('message_number')), Price(63400), Quantity(30), Timestamp(1462224447.117))
        self.declined_trade = Trade.decline(MessageId(TraderId('trader_id'), MessageNumber('message_number')), Timestamp(1462224447.117), proposed_trade)
	
    def test_to_network(self):
        # Test for to network
        self.assertEquals(
            (('trader_id',), ('trader_id', 'message_number', 'trader_id', 'message_number', 1462224447.117, False)),
            self.declined_trade.to_network())
	
    def test_from_network(self):
        # Test for from network
        data = DeclinedTrade.from_network(type('Data', (object,), {"trader_id": 'trader_id',
                                                                   "message_number": 'message_number',
                                                                   "recipient_trader_id": 'trader_id',
                                                                   "recipient_message_number": 'message_number',
                                                                   "timestamp": 1462224447.117, "quick": False,}))

        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(MessageId(TraderId('trader_id'), MessageNumber('message_number')), data.recipient_message_id)
        self.assertEquals(Timestamp(1462224447.117), data.timestamp)


if __name__ == '__main__':
    unittest.main()
