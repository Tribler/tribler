from Tribler.community.market.core import DeclinedTradeReason
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Utilities.encoding import encode
from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.payload import DeclinedTradePayload, WalletInfoPayload, PaymentPayload, \
    StartTransactionPayload, MatchPayload, AcceptMatchPayload, DeclineMatchPayload, OrderStatusRequestPayload
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMarketConversion(AbstractTestCommunity):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestMarketConversion, self).setUp(annotate=annotate)
        self.market_community = MarketCommunity(self.dispersy, self.master_member, self.member)
        self.market_community.initialize()
        self.conversion = MarketConversion(self.market_community)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        # Don't unload_community() as it never got registered in dispersy on the first place.
        self.market_community.cancel_all_pending_tasks()
        self.market_community = None
        yield super(TestMarketConversion, self).tearDown(annotate=annotate)

    def get_placeholder_msg(self, meta_name):
        """
        Return a placeholder message with a specific meta name
        """
        meta_msg = self.market_community.get_meta_message(meta_name)
        msg = MockObject()
        msg.meta = meta_msg
        return msg

    def test_decode_payload(self):
        """
        Test decoding of a payload
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"order-status-request")

        offer_payload = OrderStatusRequestPayload.Implementation(meta_msg, TraderId('abc'),
                                                                 MessageNumber('3'), Timestamp(1000), TraderId('def'),
                                                                 OrderNumber(4), 5)
        message.payload = offer_payload

        packet = encode((3.14, 100))
        placeholder = self.get_placeholder_msg(u"order-status-request")
        self.assertRaises(DropPacket, self.conversion._decode_payload, placeholder, 0, packet, [Price])
        self.assertRaises(DropPacket, self.conversion._decode_payload, placeholder, 0, "a2zz", [Price])

    def test_encode_match(self):
        """
        Test encoding and decoding of a match message
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"match")

        match_payload = MatchPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'), OrderNumber(4),
                                                    Price(1, 'BTC'), Quantity(2, 'MC'), Timeout(3600), Timestamp.now(),
                                                    '192.168.1.1', 1234, OrderNumber(3), Quantity(2, 'MC'),
                                                    TraderId('abc'), TraderId('def'), 'match_id')
        message.payload = match_payload
        packet, = self.conversion._encode_match(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_match(self.get_placeholder_msg(u"match"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.match_id, 'match_id')

    def test_encode_accept_match(self):
        """
        Test encoding and decoding of an accept-match message
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"accept-match")

        match_payload = AcceptMatchPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                          Timestamp.now(), 'match_id', Quantity(2, 'MC'))
        message.payload = match_payload
        packet, = self.conversion._encode_accept_match(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_accept_match(self.get_placeholder_msg(u"accept-match"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.match_id, 'match_id')

    def test_encode_decline_match(self):
        """
        Test encoding and decoding of a decline-match message
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"decline-match")

        match_payload = DeclineMatchPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                           Timestamp.now(), 'match_id',
                                                           DeclinedTradeReason.ORDER_COMPLETED)
        message.payload = match_payload
        packet, = self.conversion._encode_decline_match(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_decline_match(self.get_placeholder_msg(u"decline-match"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.match_id, 'match_id')
        self.assertEqual(decoded.decline_reason, DeclinedTradeReason.ORDER_COMPLETED)

    def test_encode_decode_declined_trade(self):
        """
        Test encoding and decoding of an declined trade
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"declined-trade")

        trade_payload = DeclinedTradePayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                            OrderNumber(4), TraderId('def'), OrderNumber(5), 1234,
                                                            Timestamp.now(), DeclinedTradeReason.ORDER_COMPLETED)
        message.payload = trade_payload
        packet, = self.conversion._encode_declined_trade(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_declined_trade(self.get_placeholder_msg(u"declined-trade"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.recipient_trader_id, TraderId('def'))

    def test_encode_decode_start_transaction(self):
        """
        Test encoding and decoding of a start transaction message
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"start-transaction")

        transaction_payload = StartTransactionPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                                     TraderId('def'), TransactionNumber(5),
                                                                     TraderId('def'), OrderNumber(3), TraderId('abc'),
                                                                     OrderNumber(4), 1235, Price(5, 'BTC'),
                                                                     Quantity(4, 'MC'), Timestamp.now())
        message.payload = transaction_payload
        packet, = self.conversion._encode_start_transaction(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_start_transaction(
            self.get_placeholder_msg(u"start-transaction"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.transaction_trader_id, TraderId('def'))

    def test_encode_decode_wallet_info(self):
        """
        Test encoding and decoding of wallet info
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"wallet-info")

        wallet_payload = WalletInfoPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                          TraderId('def'), TransactionNumber(5), WalletAddress('a'),
                                                          WalletAddress('b'), Timestamp.now())
        message.payload = wallet_payload
        packet, = self.conversion._encode_wallet_info(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_wallet_info(self.get_placeholder_msg(u"wallet-info"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.transaction_trader_id, TraderId('def'))

    def test_encode_decode_payment(self):
        """
        Test encoding and decoding of a payment
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"payment")

        payment_payload = PaymentPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                        TraderId('def'), TransactionNumber(5), Quantity(5, 'MC'),
                                                        Price(6, 'BTC'), WalletAddress('a'),
                                                        WalletAddress('b'), PaymentId('abc'), Timestamp.now(), False)
        message.payload = payment_payload
        packet, = self.conversion._encode_payment(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_payment(self.get_placeholder_msg(u"payment"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.transaction_trader_id, TraderId('def'))
        self.assertEqual(decoded.payment_id, PaymentId('abc'))
        self.assertEqual(decoded.success, False)

    def test_encode_decode_order_status_request(self):
        """
        Test encoding and decoding of a order status request
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"order-status-request")

        payload = OrderStatusRequestPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                           Timestamp.now(), TraderId('def'), OrderNumber(5), 1234)
        message.payload = payload
        packet, = self.conversion._encode_order_status_request(message)
        self.assertTrue(packet)

        _, decoded = self.conversion._decode_order_status_request(
            self.get_placeholder_msg(u"order-status-request"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.identifier, 1234)
