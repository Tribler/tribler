import unittest

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.transaction import TransactionNumber, TransactionId, Transaction, StartTransaction
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.core.wallet_address import WalletAddress


class TransactionNumberTestSuite(unittest.TestCase):
    """Message number test cases."""

    def setUp(self):
        # Object creation
        self.transaction_number = TransactionNumber(1)
        self.transaction_number2 = TransactionNumber(1)
        self.transaction_number3 = TransactionNumber(3)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(1, int(self.transaction_number))
        self.assertEqual('1', str(self.transaction_number))

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            TransactionNumber(1.0)

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.transaction_number == self.transaction_number2)
        self.assertTrue(self.transaction_number != self.transaction_number3)
        self.assertFalse(self.transaction_number == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.transaction_number.__hash__(), self.transaction_number2.__hash__())
        self.assertNotEqual(self.transaction_number.__hash__(), self.transaction_number3.__hash__())


class TransactionIdTestSuite(unittest.TestCase):
    """Transaction ID test cases."""

    def setUp(self):
        # Object creation
        self.transaction_id = TransactionId(TraderId('0'), TransactionNumber(1))
        self.transaction_id2 = TransactionId(TraderId('0'), TransactionNumber(1))
        self.transaction_id3 = TransactionId(TraderId('0'), TransactionNumber(2))

    def test_properties(self):
        # Test for properties
        self.assertEqual(TraderId('0'), self.transaction_id.trader_id)
        self.assertEqual(TransactionNumber(1), self.transaction_id.transaction_number)

    def test_conversion(self):
        # Test for conversions
        self.assertEqual('0.1', str(self.transaction_id))

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.transaction_id == self.transaction_id2)
        self.assertTrue(self.transaction_id != self.transaction_id3)
        self.assertFalse(self.transaction_id == 6)

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.transaction_id.__hash__(), self.transaction_id2.__hash__())
        self.assertNotEqual(self.transaction_id.__hash__(), self.transaction_id3.__hash__())


class TransactionTestSuite(unittest.TestCase):
    """Transaction test cases."""

    def setUp(self):
        # Object creation
        self.transaction_id = TransactionId(TraderId("0"), TransactionNumber(1))
        self.transaction = Transaction(self.transaction_id, AssetPair(AssetAmount(100, 'BTC'), AssetAmount(100, 'MB')),
                                       OrderId(TraderId('3'), OrderNumber(2)),
                                       OrderId(TraderId('2'), OrderNumber(1)), Timestamp(0.0))
        self.proposed_trade = Trade.propose(TraderId('0'),
                                            OrderId(TraderId('0'), OrderNumber(2)),
                                            OrderId(TraderId('1'), OrderNumber(3)),
                                            AssetPair(AssetAmount(100, 'BTC'), AssetAmount(100, 'MB')), Timestamp(0.0))
        self.payment = Payment(TraderId("0"), TransactionId(TraderId('2'), TransactionNumber(2)),
                               AssetAmount(3, 'MB'), WalletAddress('a'), WalletAddress('b'),
                               PaymentId('aaa'), Timestamp(4.0), True)

    def test_from_proposed_trade(self):
        """
        Test creating a transaction from a proposed trade
        """
        transaction = Transaction.from_proposed_trade(self.proposed_trade, self.transaction_id)
        self.assertEqual(transaction.assets, self.transaction.assets)

    def test_add_payment(self):
        """
        Test the addition of a payment to a transaction
        """
        self.transaction.add_payment(self.payment)
        self.assertEqual(self.transaction.transferred_assets.first.amount, 0)
        self.assertEqual(self.transaction.transferred_assets.second.amount, 3)
        self.assertTrue(self.transaction.payments)

    def test_next_payment(self):
        """
        Test the process of determining the next payment details during a transaction
        """
        self.assertEqual(self.transaction.next_payment(True), AssetAmount(100, 'BTC'))
        self.assertEqual(self.transaction.next_payment(False), AssetAmount(100, 'MB'))

    def test_is_payment_complete(self):
        """
        Test whether a payment is correctly marked as complete
        """
        self.assertFalse(self.transaction.is_payment_complete())
        self.transaction.add_payment(self.payment)
        self.assertFalse(self.transaction.is_payment_complete())
        self.transaction._transferred_assets = AssetPair(AssetAmount(100, 'BTC'), AssetAmount(100, 'MB'))
        self.assertTrue(self.transaction.is_payment_complete())

    def test_to_dictionary(self):
        """
        Test the to dictionary method of a transaction
        """
        self.assertDictEqual(self.transaction.to_dictionary(), {
            'trader_id': '0',
            'transaction_number': 1,
            'order_number': 2,
            'partner_trader_id': '2',
            'partner_order_number': 1,
            'payment_complete': False,
            'assets': {
                'first': {
                    'amount': 100,
                    'type': 'BTC',
                },
                'second': {
                    'amount': 100,
                    'type': 'MB'
                }
            },
            'transferred': {
                'first': {
                    'amount': 0,
                    'type': 'BTC',
                },
                'second': {
                    'amount': 0,
                    'type': 'MB'
                }
            },
            'timestamp': 0.0,
            'status': 'pending'
        })

    def test_status(self):
        """
        Test the status of a transaction
        """
        self.assertEqual(self.transaction.status, 'pending')

        self.payment._success = False
        self.transaction.add_payment(self.payment)
        self.assertEqual(self.transaction.status, 'error')


class StartTransactionTestSuite(unittest.TestCase):
    """Start transaction test cases."""

    def setUp(self):
        # Object creation
        self.start_transaction = StartTransaction(TraderId('0'),
                                                  TransactionId(TraderId("0"), TransactionNumber(1)),
                                                  OrderId(TraderId('0'), OrderNumber(1)),
                                                  OrderId(TraderId('1'), OrderNumber(1)), 1234,
                                                  AssetPair(AssetAmount(30, 'BTC'), AssetAmount(40, 'MC')),
                                                  Timestamp(0.0))

    def test_from_network(self):
        # Test for from network
        data = StartTransaction.from_network(
            type('Data', (object,), {"trader_id": TraderId('0'),
                                     "transaction_id": TransactionId(TraderId('0'), TransactionNumber(1)),
                                     "order_id": OrderId(TraderId('0'), OrderNumber(1)),
                                     "recipient_order_id": OrderId(TraderId('1'), OrderNumber(2)),
                                     "proposal_id": 1235,
                                     "assets": AssetPair(AssetAmount(30, 'BTC'), AssetAmount(40, 'MC')),
                                     "timestamp": Timestamp(0.0)}))

        self.assertEquals(TraderId("0"), data.trader_id)
        self.assertEquals(TransactionId(TraderId("0"), TransactionNumber(1)), data.transaction_id)
        self.assertEquals(OrderId(TraderId('0'), OrderNumber(1)), data.order_id)
        self.assertEquals(OrderId(TraderId('1'), OrderNumber(2)), data.recipient_order_id)
        self.assertEquals(1235, data.proposal_id)
        self.assertEquals(Timestamp(0.0), data.timestamp)

    def test_to_network(self):
        """
        Test the conversion of a StartTransaction object to the network
        """
        data = self.start_transaction.to_network()
        self.assertEqual(data[0], self.start_transaction.trader_id)
