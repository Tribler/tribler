from __future__ import absolute_import

import json

from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint
from Tribler.Core.Modules.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8


class TestMarketEndpoint(AbstractApiTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TestMarketEndpoint, self).setUp()

        dummy1_wallet = DummyWallet1()
        dummy2_wallet = DummyWallet2()
        wallets_dict = {dummy1_wallet.get_identifier(): dummy1_wallet, dummy2_wallet.get_identifier(): dummy2_wallet}
        self.mock_ipv8 = MockIPv8(u"low",
                                  MarketCommunity,
                                  create_trustchain=True,
                                  create_dht=True,
                                  wallets=wallets_dict,
                                  working_directory=self.session.config.get_state_dir())
        self.session.lm.market_community = self.mock_ipv8.overlay

    @inlineCallbacks
    def tearDown(self):
        yield self.mock_ipv8.unload()
        yield super(TestMarketEndpoint, self).tearDown()

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
        proposed_trade = Trade.propose(TraderId('0'),
                                       OrderId(TraderId('0'), OrderNumber(1)),
                                       OrderId(TraderId('1'), OrderNumber(2)),
                                       AssetPair(AssetAmount(30, 'BTC'), AssetAmount(60, 'MB')),
                                       Timestamp(1462224447.117))
        transaction = self.session.lm.market_community.transaction_manager.create_from_proposed_trade(
            proposed_trade, 'abcd')

        payment = Payment(TraderId("0"), transaction.transaction_id,
                          AssetAmount(20, 'BTC'), WalletAddress('a'), WalletAddress('b'),
                          PaymentId('aaa'), Timestamp(4.0), True)
        transaction.add_payment(payment)
        self.session.lm.market_community.transaction_manager.transaction_repository.update(transaction)

        return transaction

    def create_fake_block(self):
        """
        Create a dummy block and return it
        """
        block = MockObject()
        block.hash = 'a'
        return block

    @trial_timeout(10)
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

        self.session.lm.market_community.trustchain.send_block = lambda *_, **__: None
        self.session.lm.market_community.create_new_tick_block = lambda _: succeed((self.create_fake_block(), None))
        self.session.lm.market_community.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        self.should_check_equality = False
        return self.do_request('market/asks', expected_code=200).addCallback(on_response)

    @trial_timeout(10)
    def test_create_ask(self):
        """
        Test whether we can create an ask using the API
        """
        def on_response(_):
            self.assertEqual(len(self.session.lm.market_community.order_book.asks), 1)

        self.should_check_equality = False
        self.session.lm.market_community.trustchain.send_block = lambda *_, **__: None
        self.session.lm.market_community.create_new_tick_block = lambda _: succeed((self.create_fake_block(), None))
        post_data = {'first_asset_amount': 10, 'second_asset_amount': 10,
                     'first_asset_type': 'DUM1', 'second_asset_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/asks', expected_code=200, request_type='PUT', post_data=post_data)\
            .addCallback(on_response)

    @trial_timeout(10)
    def test_create_ask_no_amount(self):
        """
        Test for an error when we don't add an asset amount when creating an ask
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'first_asset_type': 'DUM1', 'second_asset_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/asks', expected_code=400, request_type='PUT', post_data=post_data)

    @trial_timeout(10)
    def test_create_ask_no_type(self):
        """
        Test for an error when we don't add an asset type when creating an ask
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'second_asset_amount': 10, 'second_asset_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/asks', expected_code=400, request_type='PUT', post_data=post_data)

    @trial_timeout(10)
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

        self.session.lm.market_community.trustchain.send_block = lambda *_, **__: None
        self.session.lm.market_community.create_new_tick_block = lambda _: succeed((self.create_fake_block(), None))
        self.session.lm.market_community.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        self.should_check_equality = False
        return self.do_request('market/bids', expected_code=200).addCallback(on_response)

    @trial_timeout(10)
    def test_create_bid(self):
        """
        Test whether we can create a bid using the API
        """
        def on_response(_):
            self.assertEqual(len(self.session.lm.market_community.order_book.bids), 1)

        self.should_check_equality = False
        self.session.lm.market_community.trustchain.send_block = lambda *_, **__: None
        self.session.lm.market_community.create_new_tick_block = lambda _: succeed((self.create_fake_block(), None))
        post_data = {'first_asset_amount': 10, 'second_asset_amount': 10,
                     'first_asset_type': 'DUM1', 'second_asset_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/bids', expected_code=200, request_type='PUT', post_data=post_data) \
            .addCallback(on_response)

    @trial_timeout(10)
    def test_create_bid_no_amount(self):
        """
        Test for an error when we don't add an asset amount when creating a bid
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'first_asset_type': 'DUM1', 'second_asset_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/bids', expected_code=400, request_type='PUT', post_data=post_data)

    @trial_timeout(10)
    def test_create_bid_no_type(self):
        """
        Test for an error when we don't add an asset type when creating a bid
        """
        self.should_check_equality = False
        post_data = {'first_asset_amount': 10, 'second_asset_amount': 10, 'second_asset_type': 'DUM2', 'timeout': 3400}
        return self.do_request('market/bids', expected_code=400, request_type='PUT', post_data=post_data)

    @trial_timeout(10)
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

    @trial_timeout(10)
    def test_get_payment_not_found(self):
        """
        Test whether the API returns a 404 when a payment cannot be found
        """
        self.should_check_equality = False
        return self.do_request('market/transactions/abc/3/payments', expected_code=404)

    @trial_timeout(10)
    def test_get_orders(self):
        """
        Test whether the API returns the right orders when we perform a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('orders', json_response)
            self.assertEqual(len(json_response['orders']), 1)

        self.session.lm.market_community.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(3600))

        self.should_check_equality = False
        return self.do_request('market/orders', expected_code=200).addCallback(on_response)

    @trial_timeout(10)
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

    @trial_timeout(10)
    def test_cancel_order_not_found(self):
        """
        Test whether a 404 is returned when we try to cancel an order that does not exist
        """
        self.session.lm.market_community.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(3600))
        self.should_check_equality = False
        return self.do_request('market/orders/1234/cancel', request_type='POST', expected_code=404)

    @trial_timeout(10)
    def test_cancel_order_invalid(self):
        """
        Test whether an error is returned when we try to cancel an order that has expired
        """
        order = self.session.lm.market_community.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(0))
        order.set_verified()
        self.session.lm.market_community.order_manager.order_repository.update(order)
        self.should_check_equality = False
        return self.do_request('market/orders/1/cancel', request_type='POST', expected_code=400)

    @trial_timeout(10)
    def test_cancel_order(self):
        """
        Test whether an error is returned when we try to cancel an order that has expired
        """
        order = self.session.lm.market_community.order_manager.create_ask_order(
            AssetPair(AssetAmount(3, 'DUM1'), AssetAmount(4, 'DUM2')), Timeout(3600))

        def on_response(response):
            json_response = json.loads(response)
            self.assertTrue(json_response['cancelled'])
            cancelled_order = self.session.lm.market_community.order_manager.order_repository.find_by_id(order.order_id)
            self.assertTrue(cancelled_order.cancelled)

        self.should_check_equality = False
        return self.do_request('market/orders/1/cancel', request_type='POST', expected_code=200)\
            .addCallback(on_response)

    @trial_timeout(10)
    def test_get_matchmakers(self):
        """
        Test the request to fetch known matchmakers
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertGreaterEqual(len(json_response['matchmakers']), 1)

        self.session.lm.market_community.matchmakers.add(self.session.lm.market_community.my_peer)
        self.should_check_equality = False
        return self.do_request('market/matchmakers', expected_code=200).addCallback(on_response)
