import unittest

from Tribler.community.market.core import DeclinedTradeReason, DeclineMatchReason
from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber
from Tribler.community.market.core.ttl import Ttl
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.payload import DeclinedTradePayload, TradePayload, \
    OfferPayload, StartTransactionPayload, PaymentPayload, WalletInfoPayload, MarketIntroPayload, CancelOrderPayload, \
    MatchPayload, AcceptMatchPayload, DeclineMatchPayload, TransactionCompletedPayload
from Tribler.dispersy.meta import MetaObject


class MarketIntroPayloadTestSuite(unittest.TestCase):
    """Market intro payload test cases."""

    def setUp(self):
        # Object creation
        self.market_intro_payload = MarketIntroPayload.Implementation(MetaObject(), ("a", 1324), ("b", 1234),
                                                                      ("c", 1234), True, u"public", None, 3, True, "f")

    def test_properties(self):
        """
        Test the market intro payload
        """
        self.assertTrue(self.market_intro_payload.is_matchmaker)
        self.assertEqual(self.market_intro_payload.orders_bloom_filter, "f")
        self.market_intro_payload.set_orders_bloom_filter("g")
        self.assertEqual(self.market_intro_payload.orders_bloom_filter, "g")


class CancelOrderPayloadTestSuite(unittest.TestCase):
    """Cancel order payload test cases."""

    def setUp(self):
        # Object creation
        self.cancel_order_payload = CancelOrderPayload.Implementation(MetaObject(), TraderId('0'),
                                                                      MessageNumber('message_number'), Timestamp.now(),
                                                                      OrderNumber(1), Ttl(2))

    def test_properties(self):
        # Test for properties
        self.assertEquals(OrderNumber(1), self.cancel_order_payload.order_number)
        self.assertEquals(2, int(self.cancel_order_payload.ttl))


class DeclinedTradePayloadTestSuite(unittest.TestCase):
    """Declined trade payload test cases."""

    def setUp(self):
        # Object creation
        self.declined_trade_payload = DeclinedTradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                          MessageNumber('message_number'),
                                                                          OrderNumber(1), TraderId('1'),
                                                                          OrderNumber(2), 1234,
                                                                          Timestamp(1462224447.117),
                                                                          DeclinedTradeReason.ORDER_COMPLETED)

    def test_properties(self):
        # Test for properties
        self.assertEquals(MessageNumber('message_number'), self.declined_trade_payload.message_number)
        self.assertEquals(OrderNumber(1), self.declined_trade_payload.order_number)
        self.assertEquals(OrderNumber(2), self.declined_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.declined_trade_payload.recipient_trader_id)
        self.assertEquals(Timestamp(1462224447.117), self.declined_trade_payload.timestamp)
        self.assertEquals(1234, self.declined_trade_payload.proposal_id)
        self.assertEquals(TraderId('0'), self.declined_trade_payload.trader_id)
        self.assertEquals(DeclinedTradeReason.ORDER_COMPLETED, self.declined_trade_payload.decline_reason)


class ProposedTradePayloadTestSuite(unittest.TestCase):
    """Proposed trade payload test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade_payload = TradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                  MessageNumber('message_number'),
                                                                  OrderNumber(1), TraderId('1'),
                                                                  OrderNumber(2), 1235,
                                                                  Price(63400, 'BTC'), Quantity(30, 'MC'),
                                                                  Timestamp(1462224447.117), '192.168.1.1', 1234)

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400, 'BTC'), self.proposed_trade_payload.price)
        self.assertEquals(Quantity(30, 'MC'), self.proposed_trade_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.proposed_trade_payload.message_number)
        self.assertEquals(OrderNumber(1), self.proposed_trade_payload.order_number)
        self.assertEquals(OrderNumber(2), self.proposed_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.proposed_trade_payload.recipient_trader_id)
        self.assertEquals(1235, self.proposed_trade_payload.proposal_id)
        self.assertEquals(Timestamp(1462224447.117), self.proposed_trade_payload.timestamp)
        self.assertEquals(TraderId('0'), self.proposed_trade_payload.trader_id)


class OfferPayloadTestSuite(unittest.TestCase):
    """Offer payload test cases."""

    def setUp(self):
        # Object creation
        self.offer_payload = OfferPayload.Implementation(MetaObject(), TraderId('0'), MessageNumber('message_number'),
                                                         OrderNumber(1), Price(63400, 'BTC'),
                                                         Quantity(30, 'MC'), Timeout(1470004447.117),
                                                         Timestamp(1462224447.117), 'a', 'b', Ttl(2), "1.1.1.1", 1)

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400, 'BTC'), self.offer_payload.price)
        self.assertEquals(Quantity(30, 'MC'), self.offer_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.offer_payload.message_number)
        self.assertEquals(OrderNumber(1), self.offer_payload.order_number)
        self.assertEquals(1470004447.117, float(self.offer_payload.timeout))
        self.assertEquals(Timestamp(1462224447.117), self.offer_payload.timestamp)
        self.assertEquals('a', self.offer_payload.public_key)
        self.assertEquals('b', self.offer_payload.signature)
        self.assertEquals(2, int(self.offer_payload.ttl))
        self.assertEquals(TraderId('0'), self.offer_payload.trader_id)
        self.assertEquals(1, self.offer_payload.address.port)
        self.assertEquals("1.1.1.1", self.offer_payload.address.ip)


class StartTransactionPayloadTestSuite(unittest.TestCase):
    """Start tranasaction payload test cases."""

    def setUp(self):
        # Object creation
        self.start_transaction_payload = StartTransactionPayload.Implementation(MetaObject(), TraderId('0'),
                                                                                MessageNumber('1'), TraderId('2'),
                                                                                TransactionNumber(2), TraderId('2'),
                                                                                OrderNumber(3), TraderId('0'),
                                                                                OrderNumber(4), 1236, Price(2, 'BTC'),
                                                                                Quantity(3, 'MC'), Timestamp(0.0))

    def test_properties(self):
        """
        Test the start transaction payload
        """
        self.assertEquals(MessageNumber('1'), self.start_transaction_payload.message_number)
        self.assertEquals(TransactionNumber(2), self.start_transaction_payload.transaction_number)
        self.assertEquals(Timestamp(0.0), self.start_transaction_payload.timestamp)
        self.assertEquals(TraderId('2'), self.start_transaction_payload.transaction_trader_id)
        self.assertEquals(TraderId('2'), self.start_transaction_payload.order_trader_id)
        self.assertEquals(OrderNumber(3), self.start_transaction_payload.order_number)
        self.assertEquals(TraderId('0'), self.start_transaction_payload.recipient_trader_id)
        self.assertEquals(OrderNumber(4), self.start_transaction_payload.recipient_order_number)
        self.assertEquals(1236, self.start_transaction_payload.proposal_id)
        self.assertEquals(Price(2, 'BTC'), self.start_transaction_payload.price)
        self.assertEquals(Quantity(3, 'MC'), self.start_transaction_payload.quantity)


class PaymentPayloadTestSuite(unittest.TestCase):
    """Payment payload test cases."""

    def setUp(self):
        # Object creation
        self.payment_payload = PaymentPayload.Implementation(MetaObject(), TraderId('0'), MessageNumber('1'),
                                                             TraderId('2'), TransactionNumber(2), Quantity(20, 'MC'),
                                                             Price(10, 'BTC'), WalletAddress('a'), WalletAddress('b'),
                                                             PaymentId('3'), Timestamp(0.0), True)

    def test_properties(self):
        """
        Test the payment payload
        """
        self.assertEquals(MessageNumber('1'), self.payment_payload.message_number)
        self.assertEquals(TransactionNumber(2), self.payment_payload.transaction_number)
        self.assertEquals(Price(10, 'BTC'), self.payment_payload.transferee_price)
        self.assertEquals(Quantity(20, 'MC'), self.payment_payload.transferee_quantity)
        self.assertEquals('3', str(self.payment_payload.payment_id))
        self.assertEquals(Timestamp(0.0), self.payment_payload.timestamp)
        self.assertEquals(WalletAddress('a'), self.payment_payload.address_from)
        self.assertEquals(WalletAddress('b'), self.payment_payload.address_to)
        self.assertEquals(True, self.payment_payload.success)


class WalletInfoPayloadTestSuite(unittest.TestCase):
    """Wallet info payload test cases."""

    def setUp(self):
        # Object creation
        self.wallet_info_payload = WalletInfoPayload.Implementation(MetaObject(), TraderId('0'), MessageNumber('1'),
                                                                    TraderId('2'), TransactionNumber(2),
                                                                    WalletAddress('a'), WalletAddress('b'),
                                                                    Timestamp(3600.0))

    def test_properties(self):
        """
        Test the wallet info payload
        """
        self.assertEquals(WalletAddress('a'), self.wallet_info_payload.incoming_address)
        self.assertEquals(WalletAddress('b'), self.wallet_info_payload.outgoing_address)


class MatchPayloadTestSuite(unittest.TestCase):
    """Match payload test cases."""

    def setUp(self):
        # Object creation
        self.match_payload = MatchPayload.Implementation(MetaObject(), TraderId('0'), MessageNumber('message_number'),
                                                         OrderNumber(1), Price(63400, 'BTC'),
                                                         Quantity(30, 'MC'), Timeout(1470004447.117),
                                                         Timestamp(1462224447.117), 'a', 'b', Ttl(2), "1.1.1.1", 1,
                                                         OrderNumber(2), Quantity(20, 'MC'), TraderId('1'),
                                                         TraderId('2'), 'a')

    def test_properties(self):
        """
        Test the wallet info payload
        """
        self.assertEquals(OrderNumber(2), self.match_payload.recipient_order_number)
        self.assertEquals(Quantity(20, 'MC'), self.match_payload.match_quantity)
        self.assertEquals(TraderId('1'), self.match_payload.match_trader_id)
        self.assertEquals(TraderId('2'), self.match_payload.matchmaker_trader_id)
        self.assertEquals('a', self.match_payload.match_id)


class AcceptMatchPayloadTestSuite(unittest.TestCase):
    """Accept match payload test cases."""

    def setUp(self):
        # Object creation
        self.accept_match_payload = AcceptMatchPayload.Implementation(MetaObject(), TraderId('0'),
                                                                      MessageNumber('message_number'), Timestamp.now(),
                                                                      'a', Quantity(20, 'MC'))

    def test_properties(self):
        # Test for properties
        self.assertEquals('a', self.accept_match_payload.match_id)
        self.assertEquals(Quantity(20, 'MC'), self.accept_match_payload.quantity)


class DeclineMatchPayloadTestSuite(unittest.TestCase):
    """Decline match payload test cases."""

    def setUp(self):
        # Object creation
        self.decline_match_payload = DeclineMatchPayload.Implementation(MetaObject(), TraderId('0'),
                                                                        MessageNumber('message_number'),
                                                                        Timestamp.now(), 'a',
                                                                        DeclineMatchReason.ORDER_COMPLETED)

    def test_properties(self):
        # Test for properties
        self.assertEquals('a', self.decline_match_payload.match_id)
        self.assertEquals(DeclineMatchReason.ORDER_COMPLETED, self.decline_match_payload.decline_reason)


class TransactionCompletedPayloadTestSuite(unittest.TestCase):
    """Tranasaction completed payload test cases."""

    def setUp(self):
        # Object creation
        self.transaction_completed_payload = TransactionCompletedPayload.Implementation(MetaObject(), TraderId('0'),
                                                                                        MessageNumber('1'),
                                                                                        TraderId('2'),
                                                                                        TransactionNumber(2),
                                                                                        TraderId('2'),
                                                                                        OrderNumber(3),
                                                                                        TraderId('0'),
                                                                                        OrderNumber(4),
                                                                                        'a', Quantity(20, 'MC'),
                                                                                        Timestamp(0.0))

    def test_properties(self):
        """
        Test the transaction completed payload
        """
        self.assertEquals(TraderId('2'), self.transaction_completed_payload.order_trader_id)
        self.assertEquals(OrderNumber(3), self.transaction_completed_payload.order_number)
        self.assertEquals(TraderId('0'), self.transaction_completed_payload.recipient_trader_id)
        self.assertEquals(OrderNumber(4), self.transaction_completed_payload.recipient_order_number)
        self.assertEquals('a', self.transaction_completed_payload.match_id)
        self.assertEquals(Quantity(20, 'MC'), self.transaction_completed_payload.quantity)
