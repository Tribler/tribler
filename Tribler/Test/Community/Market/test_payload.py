import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.payload import AcceptedTradePayload, DeclinedTradePayload, ProposedTradePayload, \
    OfferPayload
from Tribler.community.market.socket_address import SocketAddress
from Tribler.community.market.ttl import Ttl
from Tribler.dispersy.meta import MetaObject


class AcceptedTradePayloadTestSuite(unittest.TestCase):
    """Accepted trade payload test cases."""

    def setUp(self):
        # Object creation
        self.accepted_trade_payload = AcceptedTradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                          MessageNumber('message_number'),
                                                                          OrderNumber('order_number'), TraderId('1'),
                                                                          OrderNumber('recipient_order_number'),
                                                                          Price(63400), Quantity(30),
                                                                          Timestamp(1462224447.117), Ttl(2))

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400), self.accepted_trade_payload.price)
        self.assertEquals(Quantity(30), self.accepted_trade_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.accepted_trade_payload.message_number)
        self.assertEquals(OrderNumber('order_number'), self.accepted_trade_payload.order_number)
        self.assertEquals(OrderNumber('recipient_order_number'), self.accepted_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.accepted_trade_payload.recipient_trader_id)
        self.assertEquals(Timestamp(1462224447.117), self.accepted_trade_payload.timestamp)
        self.assertEquals(Ttl(2), self.accepted_trade_payload.ttl)
        self.assertEquals(TraderId('0'), self.accepted_trade_payload.trader_id)


class DeclinedTradePayloadTestSuite(unittest.TestCase):
    """Declined trade payload test cases."""

    def setUp(self):
        # Object creation
        self.declined_trade_payload = DeclinedTradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                          MessageNumber('message_number'),
                                                                          OrderNumber('order_number'), TraderId('1'),
                                                                          OrderNumber('recipient_order_number'),
                                                                          Timestamp(1462224447.117))

    def test_properties(self):
        # Test for properties
        self.assertEquals(MessageNumber('message_number'), self.declined_trade_payload.message_number)
        self.assertEquals(OrderNumber('order_number'), self.declined_trade_payload.order_number)
        self.assertEquals(OrderNumber('recipient_order_number'), self.declined_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.declined_trade_payload.recipient_trader_id)
        self.assertEquals(Timestamp(1462224447.117), self.declined_trade_payload.timestamp)
        self.assertEquals(TraderId('0'), self.declined_trade_payload.trader_id)


class ProposedTradePayloadTestSuite(unittest.TestCase):
    """Proposed trade payload test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade_payload = ProposedTradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                          MessageNumber('message_number'),
                                                                          OrderNumber('order_number'), TraderId('1'),
                                                                          OrderNumber('recipient_order_number'),
                                                                          Price(63400), Quantity(30),
                                                                          Timestamp(1462224447.117))

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400), self.proposed_trade_payload.price)
        self.assertEquals(Quantity(30), self.proposed_trade_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.proposed_trade_payload.message_number)
        self.assertEquals(OrderNumber('order_number'), self.proposed_trade_payload.order_number)
        self.assertEquals(OrderNumber('recipient_order_number'), self.proposed_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.proposed_trade_payload.recipient_trader_id)
        self.assertEquals(Timestamp(1462224447.117), self.proposed_trade_payload.timestamp)
        self.assertEquals(TraderId('0'), self.proposed_trade_payload.trader_id)


class OfferPayloadTestSuite(unittest.TestCase):
    """Offer payload test cases."""

    def setUp(self):
        # Object creation
        self.offer_payload = OfferPayload.Implementation(MetaObject(), TraderId('0'), MessageNumber('message_number'),
                                                         OrderNumber('order_number'), Price(63400),
                                                         Quantity(30), Timeout(1470004447.117),
                                                         Timestamp(1462224447.117), Ttl(2), SocketAddress("1.1.1.1", 1))

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400), self.offer_payload.price)
        self.assertEquals(Quantity(30), self.offer_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.offer_payload.message_number)
        self.assertEquals(OrderNumber('order_number'), self.offer_payload.order_number)
        self.assertEquals(1470004447.117, float(self.offer_payload.timeout))
        self.assertEquals(Timestamp(1462224447.117), self.offer_payload.timestamp)
        self.assertEquals(Ttl(2), self.offer_payload.ttl)
        self.assertEquals(TraderId('0'), self.offer_payload.trader_id)
        self.assertEquals(SocketAddress("1.1.1.1", 1), self.offer_payload.address)


if __name__ == '__main__':
    unittest.main()
