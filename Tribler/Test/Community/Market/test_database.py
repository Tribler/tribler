from __future__ import absolute_import

import os

import six

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import Transaction, TransactionId, TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.database import LATEST_DB_VERSION, MarketDB


class TestDatabase(AbstractServer):

    @inlineCallbacks
    def setUp(self):
        yield super(TestDatabase, self).setUp()

        path = os.path.join(self.getStateDir(), 'sqlite')
        if not os.path.exists(path):
            os.makedirs(path)

        self.database = MarketDB(self.getStateDir(), 'market')

        self.order_id1 = OrderId(TraderId(b'3'), OrderNumber(4))
        self.order_id2 = OrderId(TraderId(b'4'), OrderNumber(5))
        self.order1 = Order(self.order_id1, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                            Timeout(3600), Timestamp.now(), True)
        self.order2 = Order(self.order_id2, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                            Timeout(3600), Timestamp.now(), False)
        self.order2.reserve_quantity_for_tick(OrderId(TraderId(b'3'), OrderNumber(4)), 3)

        self.transaction_id1 = TransactionId(TraderId(b"0"), TransactionNumber(4))
        self.transaction1 = Transaction(self.transaction_id1, AssetPair(AssetAmount(100, 'BTC'), AssetAmount(30, 'MB')),
                                        OrderId(TraderId(b"0"), OrderNumber(1)),
                                        OrderId(TraderId(b"1"), OrderNumber(2)), Timestamp(20.0))

        self.payment1 = Payment(TraderId(b"0"), self.transaction_id1, AssetAmount(5, 'BTC'),
                                WalletAddress('abc'), WalletAddress('def'), PaymentId("abc"), Timestamp(20.0), False)

        self.transaction1.add_payment(self.payment1)

    def test_add_get_order(self):
        """
        Test the insertion and retrieval of an order in the database
        """
        self.database.add_order(self.order1)
        self.database.add_order(self.order2)
        orders = self.database.get_all_orders()
        self.assertEqual(len(orders), 2)

    def test_get_specific_order(self):
        """
        Test the retrieval of a specific order
        """
        order_id = OrderId(TraderId(b'3'), OrderNumber(4))
        self.assertIsNone(self.database.get_order(order_id))
        self.database.add_order(self.order1)
        self.assertIsNotNone(self.database.get_order(order_id))

    def test_delete_order(self):
        """
        Test the deletion of an order from the database
        """
        self.database.add_order(self.order1)
        self.assertEqual(len(self.database.get_all_orders()), 1)
        self.database.delete_order(self.order_id1)
        self.assertEqual(len(self.database.get_all_orders()), 0)

    def test_get_next_order_number(self):
        """
        Test the retrieval of the next order number from the database
        """
        self.assertEqual(self.database.get_next_order_number(), 1)
        self.database.add_order(self.order1)
        self.assertEqual(self.database.get_next_order_number(), 5)

    def test_add_delete_reserved_ticks(self):
        """
        Test the retrieval, addition and deletion of reserved ticks in the database
        """
        self.database.add_reserved_tick(self.order_id1, self.order_id2, self.order1.total_quantity)
        self.assertEqual(len(self.database.get_reserved_ticks(self.order_id1)), 1)
        self.database.delete_reserved_ticks(self.order_id1)
        self.assertEqual(len(self.database.get_reserved_ticks(self.order_id1)), 0)

    def test_add_get_transaction(self):
        """
        Test the insertion and retrieval of a transaction in the database
        """
        self.database.add_transaction(self.transaction1)
        transactions = self.database.get_all_transactions()
        self.assertEqual(len(transactions), 1)
        self.assertEqual(len(self.database.get_payments(self.transaction1.transaction_id)), 1)

    def test_insert_or_update_transaction(self):
        """
        Test the conditional insertion or update of a transaction in the database
        """
        # Test insertion
        self.database.insert_or_update_transaction(self.transaction1)
        transactions = self.database.get_all_transactions()
        self.assertEqual(len(transactions), 1)

        # Test try to update with older timestamp
        before_trans1 = Transaction(self.transaction1.transaction_id, self.transaction1.assets,
                                    self.transaction1.order_id, self.transaction1.partner_order_id,
                                    Timestamp(float(self.transaction1.timestamp) - 1.0))
        self.database.insert_or_update_transaction(before_trans1)
        transaction = self.database.get_transaction(self.transaction1.transaction_id)
        self.assertEqual(float(transaction.timestamp), float(self.transaction1.timestamp))

        # Test update with newer timestamp
        after_trans1 = Transaction(self.transaction1.transaction_id, self.transaction1.assets,
                                   self.transaction1.order_id, self.transaction1.partner_order_id,
                                   Timestamp(float(self.transaction1.timestamp) + 1.0))
        self.database.insert_or_update_transaction(after_trans1)
        transaction = self.database.get_transaction(self.transaction1.transaction_id)
        self.assertEqual(float(transaction.timestamp), float(after_trans1.timestamp))

    def test_get_specific_transaction(self):
        """
        Test the retrieval of a specific transaction
        """
        transaction_id = TransactionId(TraderId(b'0'), TransactionNumber(4))
        self.assertIsNone(self.database.get_transaction(transaction_id))
        self.database.add_transaction(self.transaction1)
        self.assertIsNotNone(self.database.get_transaction(transaction_id))

    def test_delete_transaction(self):
        """
        Test the deletion of a transaction from the database
        """
        self.database.add_transaction(self.transaction1)
        self.assertEqual(len(self.database.get_all_transactions()), 1)
        self.database.delete_transaction(self.transaction_id1)
        self.assertEqual(len(self.database.get_all_transactions()), 0)

    def test_get_next_transaction_number(self):
        """
        Test the retrieval of the next transaction number from the database
        """
        self.assertEqual(self.database.get_next_transaction_number(), 1)
        self.database.add_transaction(self.transaction1)
        self.assertEqual(self.database.get_next_transaction_number(), 5)

    def test_add_get_payment(self):
        """
        Test the insertion and retrieval of a payment in the database
        """
        self.database.add_payment(self.payment1)
        payments = self.database.get_payments(self.transaction_id1)
        self.assertEqual(len(payments), 1)

    def test_add_remove_tick(self):
        """
        Test addition, retrieval and deletion of ticks in the database
        """
        ask = Tick.from_order(self.order1)
        self.database.add_tick(ask)
        bid = Tick.from_order(self.order2)
        self.database.add_tick(bid)

        self.assertEqual(len(self.database.get_ticks()), 2)

        self.database.delete_all_ticks()
        self.assertEqual(len(self.database.get_ticks()), 0)

    def test_add_get_trader_identity(self):
        """
        Test the addition and retrieval of a trader identity in the database
        """
        self.database.add_trader_identity(TraderId(b"a"), "123", 1234)
        self.database.add_trader_identity(TraderId(b"b"), "124", 1235)
        traders = self.database.get_traders()
        self.assertEqual(len(traders), 2)

    def test_check_database(self):
        """
        Test the check of the database
        """
        self.assertEqual(self.database.check_database(six.text_type(LATEST_DB_VERSION)), LATEST_DB_VERSION)

    def test_get_upgrade_script(self):
        """
        Test fetching the upgrade script of the database
        """
        self.assertTrue(self.database.get_upgrade_script(1))

    def test_db_upgrade(self):
        self.database.execute(u"DROP TABLE orders;")
        self.database.execute(u"DROP TABLE ticks;")
        self.database.execute(u"CREATE TABLE orders(x INTEGER PRIMARY KEY ASC);")
        self.database.execute(u"CREATE TABLE ticks(x INTEGER PRIMARY KEY ASC);")
        self.assertEqual(self.database.check_database(u"1"), 3)
