from nose.twistedtools import deferred
from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Core.Modules.wallet.dummy_wallet import BaseDummyWallet, DummyWallet1, DummyWallet2
from Tribler.Core.Modules.wallet.wallet import InsufficientFunds
from Tribler.Test.test_as_server import AbstractServer


class TestDummyWallet(AbstractServer):

    @inlineCallbacks
    def setUp(self):
        yield super(TestDummyWallet, self).setUp()
        self.dummy_wallet = BaseDummyWallet()

    def test_wallet_id(self):
        """
        Test the identifier of a dummy wallet
        """
        self.assertEqual(self.dummy_wallet.get_identifier(), 'DUM')
        self.assertEqual(DummyWallet1().get_identifier(), 'DUM1')
        self.assertEqual(DummyWallet2().get_identifier(), 'DUM2')

    def test_wallet_name(self):
        """
        Test the name of a dummy wallet
        """
        self.assertEqual(self.dummy_wallet.get_name(), 'Dummy')
        self.assertEqual(DummyWallet1().get_name(), 'Dummy 1')
        self.assertEqual(DummyWallet2().get_name(), 'Dummy 2')

    @deferred(timeout=10)
    def test_create_wallet(self):
        """
        Test the creation of a dummy wallet
        """
        return self.dummy_wallet.create_wallet()

    @deferred(timeout=10)
    def test_get_balance(self):
        """
        Test fetching the balance of a dummy wallet
        """
        def on_balance(balance):
            self.assertIsInstance(balance, dict)

        return self.dummy_wallet.get_balance().addCallback(on_balance)

    @deferred(timeout=10)
    def test_transfer(self):
        """
        Test the transfer of money from a dummy wallet
        """
        def check_transactions(transactions):
            self.assertEqual(len(transactions), 1)

        def get_transactions(_):
            return self.dummy_wallet.get_transactions().addCallback(check_transactions)

        return self.dummy_wallet.transfer(self.dummy_wallet.balance - 1, None).addCallback(get_transactions)

    @deferred(timeout=10)
    def test_transfer_invalid(self):
        """
        Test whether transferring a too large amount of money from a dummy wallet raises an error
        """
        test_deferred = Deferred()

        def on_error(failure):
            self.assertIsInstance(failure.value, InsufficientFunds)
            test_deferred.callback(None)

        self.dummy_wallet.transfer(self.dummy_wallet.balance + 1, None).addErrback(on_error)
        return test_deferred

    @deferred(timeout=10)
    def test_monitor(self):
        """
        Test the monitor loop of a transaction wallet
        """
        self.dummy_wallet.MONITOR_DELAY = 1
        return self.dummy_wallet.monitor_transaction("3.0")

    @deferred(timeout=10)
    def test_monitor_instant(self):
        """
        Test an instant the monitor loop of a transaction wallet
        """
        self.dummy_wallet.MONITOR_DELAY = 0
        return self.dummy_wallet.monitor_transaction("3.0")

    def test_address(self):
        """
        Test the address of a dummy wallet
        """
        self.assertIsInstance(self.dummy_wallet.get_address(), str)

    @deferred(timeout=10)
    def test_get_transaction(self):
        """
        Test the retrieval of transactions of a dummy wallet
        """
        def on_transactions(transactions):
            self.assertIsInstance(transactions, list)

        return self.dummy_wallet.get_transactions().addCallback(on_transactions)

    def test_min_unit(self):
        """
        Test the minimum unit of a dummy wallet
        """
        self.assertEqual(self.dummy_wallet.min_unit(), 1)

    def test_generate_txid(self):
        """
        Test the generation of a random transaction id
        """
        self.assertTrue(self.dummy_wallet.generate_txid(10))
        self.assertEqual(len(self.dummy_wallet.generate_txid(20)), 20)
