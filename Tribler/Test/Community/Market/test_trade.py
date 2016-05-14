import unittest


from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.trade import Trade, ProposedTrade, DeclinedTrade, AcceptedTrade


class TradeTestSuite(unittest.TestCase):
    """Trade test cases."""

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