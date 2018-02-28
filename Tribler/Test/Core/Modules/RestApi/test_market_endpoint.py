import json

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred
from Tribler.community.market.core.message import MessageId, MessageNumber
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMarketEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestMarketEndpoint, self).setUp(autoload_discovery=autoload_discovery)
        self.session.lm.market_community._use_main_thread = False
        dummy1_wallet = DummyWallet1()
        dummy2_wallet = DummyWallet2()

        self.session.lm.market_community.wallets = {dummy1_wallet.get_identifier(): dummy1_wallet,
                                                    dummy2_wallet.get_identifier(): dummy2_wallet}

    def test_get_market_community(self):
        """
        Test the method to get the market community in the market API
        """
        endpoint = BaseMarketEndpoint(self.session)
        self.session.lm.market_community = None
        self.assertRaises(RuntimeError, endpoint.get_market_community)

    def add_transaction_and_payment(self):
        """
        Add a transaction and a payment to the market
        """
        proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber(1)),
                                       OrderId(TraderId('0'), OrderNumber(1)),
                                       OrderId(TraderId('1'), OrderNumber(2)),
                                       Price(63400, 'BTC'), Quantity(30, 'MC'), Timestamp(1462224447.117))
        transaction = self.session.lm.market_community.transaction_manager.create_from_proposed_trade(
            proposed_trade, 'abcd')

        payment = Payment(MessageId(TraderId("0"), MessageNumber(1)), transaction.transaction_id,
                          Quantity(0, 'MC'), Price(20, 'BTC'), WalletAddress('a'), WalletAddress('b'),
                          PaymentId('aaa'), Timestamp(4.0), True)
        transaction.add_payment(payment)
        self.session.lm.market_community.transaction_manager.transaction_repository.update(transaction)

        return transaction

    @blocking_call_on_reactor_thread
    def setUpPreSession(self):
        super(TestMarketEndpoint, self).setUpPreSession()
        self.config.set_dispersy_enabled(False)
        self.config.set_ipv8_enabled(True)

    @deferred(timeout=10)
    def test_get_asks(self):
        """
        Test whether the API returns the right asks in the order book when performing a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('asks', json_response)
            self.assertEqual(len(json_response['asks']), 1)
            self.assertIn('ticks', json_response['asks'][0])
            self.assertEqual(len(json_response['asks'][0]['ticks']), 1)

        self.session.lm.market_community.create_ask(10, 'DUM1', 10, 'DUM2', 3600)
        self.should_check_equality = False
        return self.do_request('market/asks', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_create_ask(self):
        """
        Test whether we can create an ask using the API
        """
        def on_response(_):
            self.assertEqual(len(self.session.lm.market_community.order_book.asks), 1)

        self.should_check_equality = False
        post_data = {'price': 10, 'quantity': 10, 'price_type': 'DUM1', 'quantity_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/asks', expected_code=200, request_type='PUT', post_data=post_data)\
            .addCallback(on_response)

    @deferred(timeout=10)
    def test_create_ask_no_price(self):
        """
        Test for an error when we don't add a price when creating an ask
        """
        self.should_check_equality = False
        post_data = {'quantity': 10, 'price_type': 'DUM1', 'quantity_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/asks', expected_code=400, request_type='PUT', post_data=post_data)

    @deferred(timeout=10)
    def test_create_ask_no_price_type(self):
        """
        Test for an error when we don't add a price type when creating an ask
        """
        self.should_check_equality = False
        post_data = {'price': 10, 'quantity': 10, 'quantity_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/asks', expected_code=400, request_type='PUT', post_data=post_data)

    @deferred(timeout=10)
    def test_get_bids(self):
        """
        Test whether the API returns the right bids in the order book when performing a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('bids', json_response)
            self.assertEqual(len(json_response['bids']), 1)
            self.assertIn('ticks', json_response['bids'][0])
            self.assertEqual(len(json_response['bids'][0]['ticks']), 1)

        self.session.lm.market_community.create_bid(10, 'DUM1', 10, 'DUM2', 3600)
        self.should_check_equality = False
        return self.do_request('market/bids', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_create_bid(self):
        """
        Test whether we can create a bid using the API
        """
        def on_response(_):
            self.assertEqual(len(self.session.lm.market_community.order_book.bids), 1)

        self.should_check_equality = False
        post_data = {'price': 10, 'quantity': 10, 'price_type': 'DUM1', 'quantity_type': 'DUM2'}
        return self.do_request('market/bids', expected_code=200, request_type='PUT', post_data=post_data) \
            .addCallback(on_response)

    @deferred(timeout=10)
    def test_create_bid_no_price(self):
        """
        Test for an error when we don't add a price when creating a bid
        """
        self.should_check_equality = False
        post_data = {'quantity': 10, 'price_type': 'DUM1', 'quantity_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/bids', expected_code=400, request_type='PUT', post_data=post_data)

    @deferred(timeout=10)
    def test_create_bid_no_price_type(self):
        """
        Test for an error when we don't add a price type when creating a bid
        """
        self.should_check_equality = False
        post_data = {'price': 10, 'quantity': 10, 'quantity_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/bids', expected_code=400, request_type='PUT', post_data=post_data)

    @deferred(timeout=10)
    def test_get_transactions(self):
        """
        Test whether the API returns the right transactions in the order book when performing a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('transactions', json_response)
            self.assertEqual(len(json_response['transactions']), 1)

        self.add_transaction_and_payment()
        self.should_check_equality = False
        return self.do_request('market/transactions', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_get_payment_not_found(self):
        """
        Test whether the API returns a 404 when a payment cannot be found
        """
        self.should_check_equality = False
        return self.do_request('market/transactions/abc/3/payments', expected_code=404)

    @deferred(timeout=10)
    def test_get_orders(self):
        """
        Test whether the API returns the right orders when we perform a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('orders', json_response)
            self.assertEqual(len(json_response['orders']), 1)

        self.session.lm.market_community.order_manager.create_ask_order(
            Price(3, 'DUM1'), Quantity(4, 'DUM2'), Timeout(3600))

        self.should_check_equality = False
        return self.do_request('market/orders', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_get_payments(self):
        """
        Test whether the API returns the right payments when we perform a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('payments', json_response)
            self.assertEqual(len(json_response['payments']), 1)

        transaction = self.add_transaction_and_payment()
        self.should_check_equality = False
        return self.do_request('market/transactions/%s/%s/payments' %
                               (transaction.transaction_id.trader_id, transaction.transaction_id.transaction_number),
                               expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_cancel_order_not_found(self):
        """
        Test whether a 404 is returned when we try to cancel an order that does not exist
        """
        self.session.lm.market_community.order_manager.create_ask_order(
            Price(3, 'DUM1'), Quantity(4, 'DUM2'), Timeout(3600))
        self.should_check_equality = False
        return self.do_request('market/orders/1234/cancel', request_type='POST', expected_code=404)

    @deferred(timeout=10)
    def test_cancel_order_invalid(self):
        """
        Test whether an error is returned when we try to cancel an order that has expired
        """
        self.session.lm.market_community.order_manager.create_ask_order(
            Price(3, 'DUM1'), Quantity(4, 'DUM2'), Timeout(0))
        self.should_check_equality = False
        return self.do_request('market/orders/1/cancel', request_type='POST', expected_code=400)

    @deferred(timeout=10)
    def test_cancel_order(self):
        """
        Test whether an error is returned when we try to cancel an order that has expired
        """
        order = self.session.lm.market_community.order_manager.create_ask_order(
            Price(3, 'DUM1'), Quantity(4, 'DUM2'), Timeout(3600))

        def on_response(response):
            json_response = json.loads(response)
            self.assertTrue(json_response['cancelled'])
            cancelled_order = self.session.lm.market_community.order_manager.order_repository.find_by_id(order.order_id)
            self.assertTrue(cancelled_order.cancelled)

        self.should_check_equality = False
        return self.do_request('market/orders/1/cancel', request_type='POST', expected_code=200)\
            .addCallback(on_response)
