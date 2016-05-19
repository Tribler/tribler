import unittest

from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.message import Message, TraderId, MessageNumber, MessageId
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.payload import AcceptedTradePayload, DeclinedTradePayload, ProposedTradePayload,\
    OfferPayload
from Tribler.dispersy.meta import MetaObject


class AcceptedTradePayloadTestSuite(unittest.TestCase):
    """Accepted trade payload test cases."""

    def setUp(self):
        # Object creation
        self.accepted_trade_payload = AcceptedTradePayload.Implementation(MetaObject(), 'trader_id', 'message_number',
                                                                          'order_number', 'recipient_trader_id',
                                                                          'recipient_order_number', 63400, 30,
                                                                          1462224447.117, False, 2)

    def test_properties(self):
        # Test for properties
        self.assertEquals(63400, self.accepted_trade_payload.price)
        self.assertEquals(30, self.accepted_trade_payload.quantity)
        self.assertEquals('message_number', self.accepted_trade_payload.message_number)
        self.assertEquals('order_number', self.accepted_trade_payload.order_number)
        self.assertEquals(False, self.accepted_trade_payload.quick)
        self.assertEquals('recipient_order_number', self.accepted_trade_payload.recipient_order_number)
        self.assertEquals('recipient_trader_id', self.accepted_trade_payload.recipient_trader_id)
        self.assertEquals(1462224447.117, self.accepted_trade_payload.timestamp)
        self.assertEquals(2, self.accepted_trade_payload.ttl)
        self.assertEquals('trader_id', self.accepted_trade_payload.trader_id)


class DeclinedTradePayloadTestSuite(unittest.TestCase):
    """Declined trade payload test cases."""

    def setUp(self):
        # Object creation
        self.declined_trade_payload = DeclinedTradePayload.Implementation(MetaObject(), 'trader_id', 'message_number',
                                                                          'order_number', 'recipient_trader_id',
                                                                          'recipient_order_number', 1462224447.117,
                                                                          False)

    def test_properties(self):
        # Test for properties
        self.assertEquals('message_number', self.declined_trade_payload.message_number)
        self.assertEquals('order_number', self.declined_trade_payload.order_number)
        self.assertEquals(False, self.declined_trade_payload.quick)
        self.assertEquals('recipient_order_number', self.declined_trade_payload.recipient_order_number)
        self.assertEquals('recipient_trader_id', self.declined_trade_payload.recipient_trader_id)
        self.assertEquals(1462224447.117, self.declined_trade_payload.timestamp)
        self.assertEquals('trader_id', self.declined_trade_payload.trader_id)


class ProposedTradePayloadTestSuite(unittest.TestCase):
    """Proposed trade payload test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade_payload = ProposedTradePayload.Implementation(MetaObject(), 'trader_id', 'message_number',
                                                                          'order_number',
                                                                          'recipient_trader_id',
                                                                          'recipient_order_number', 63400, 30,
                                                                          1462224447.117, False)

    def test_properties(self):
        # Test for properties
        self.assertEquals(63400, self.proposed_trade_payload.price)
        self.assertEquals(30, self.proposed_trade_payload.quantity)
        self.assertEquals('message_number', self.proposed_trade_payload.message_number)
        self.assertEquals('order_number', self.proposed_trade_payload.order_number)
        self.assertEquals(False, self.proposed_trade_payload.quick)
        self.assertEquals('recipient_order_number', self.proposed_trade_payload.recipient_order_number)
        self.assertEquals('recipient_trader_id', self.proposed_trade_payload.recipient_trader_id)
        self.assertEquals(1462224447.117, self.proposed_trade_payload.timestamp)
        self.assertEquals('trader_id', self.proposed_trade_payload.trader_id)


class OfferPayloadTestSuite(unittest.TestCase):
    """Offer payload test cases."""

    def setUp(self):
        # Object creation
        self.offer_payload = OfferPayload.Implementation(MetaObject(), 'trader_id', 'message_number', 'order_number',
                                                         63400, 30, 1470004447.117, 1462224447.117, 2, ('address', 0))

    def test_properties(self):
        # Test for properties
        self.assertEquals(63400, self.offer_payload.price)
        self.assertEquals(30, self.offer_payload.quantity)
        self.assertEquals('message_number', self.offer_payload.message_number)
        self.assertEquals('order_number', self.offer_payload.order_number)
        self.assertEquals(1470004447.117, self.offer_payload.timeout)
        self.assertEquals(1462224447.117, self.offer_payload.timestamp)
        self.assertEquals(2, self.offer_payload.ttl)
        self.assertEquals('trader_id', self.offer_payload.trader_id)
        self.assertEquals(('address', 0), self.offer_payload.address)


if __name__ == '__main__':
    unittest.main()
