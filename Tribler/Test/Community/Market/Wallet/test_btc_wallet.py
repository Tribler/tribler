from twisted.internet.defer import inlineCallbacks, succeed, Deferred

from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from Tribler.community.market.wallet.btc_wallet import BitcoinWallet
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestBtcWallet(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestBtcWallet, self).setUp(annotate=annotate)

    @deferred(timeout=20)
    def test_btc_wallet(self):
        """
        Test the creating, opening, transactions and balance query of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir, testnet=True)

        def on_wallet_transactions(transactions):
            self.assertFalse(transactions)

            wallet.get_transactions = lambda: succeed([{"id": "abc"}])
            return wallet.monitor_transaction("abc")

        def on_wallet_balance(balance):
            self.assertDictEqual(balance, {'available': 0, 'pending': 0, 'currency': 'BTC'})
            return wallet.get_transactions().addCallback(on_wallet_transactions)

        def on_wallet_created(_):
            self.assertIsNotNone(wallet.wallet)
            self.assertTrue(wallet.get_address())

            _ = BitcoinWallet(self.session_base_dir, testnet=True)
            wallet.set_wallet_password('abc')
            self.assertRaises(Exception, BitcoinWallet, self.session_base_dir, testnet=True)

            return wallet.get_balance().addCallback(on_wallet_balance)

        return wallet.create_wallet('tribler').addCallback(on_wallet_created)

    def test_btc_wallet_name(self):
        """
        Test the name of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.get_name(), 'Bitcoin')

    def test_btc_wallet_identfier(self):
        """
        Test the identifier of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.get_identifier(), 'BTC')

    def test_btc_wallet_address(self):
        """
        Test the address of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.get_address(), '')

    def test_btc_wallet_unit(self):
        """
        Test the mininum unit of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.min_unit(), 0.0001)

    def test_btc_balance_no_wallet(self):
        """
        Test the retrieval of the balance of a BTC wallet that is not created yet
        """
        def on_wallet_balance(balance):
            self.assertDictEqual(balance, {'available': 0, 'pending': 0, 'currency': 'BTC'})

        wallet = BitcoinWallet(self.session_base_dir)
        return wallet.get_balance().addCallback(on_wallet_balance)

    @deferred(timeout=10)
    def test_btc_wallet_transfer_no_funds(self):
        """
        Test that the transfer method of a BTC wallet raises an error when we don't have enough funds
        """
        test_deferred = Deferred()

        wallet = BitcoinWallet(self.session_base_dir)
        mock_daemon = MockObject()
        wallet.get_daemon = lambda: mock_daemon

        wallet.transfer(3, 'abacd').addErrback(lambda _: test_deferred.callback(None))
        return test_deferred

    @deferred(timeout=10)
    def test_btc_wallet_transfer(self):
        """
        Test that the transfer method of a BTC wallet
        """
        def mocked_run_cmdline(request):
            if request['cmd'] == 'payto':
                return {'hex': 'abcd'}
            elif request['cmd'] == 'broadcast':
                return True, 'abcd'

        wallet = BitcoinWallet(self.session_base_dir)
        mock_daemon = MockObject()
        mock_server = MockObject()
        mock_server.run_cmdline = mocked_run_cmdline
        mock_daemon.get_server = lambda _: mock_server
        wallet.get_daemon = lambda: mock_daemon
        wallet.get_balance = lambda: succeed({'available': 5})

        return wallet.transfer(3, 'abacd')

    @deferred(timeout=10)
    def test_btc_wallet_transfer_error(self):
        """
        Test that the transfer method of a BTC wallet
        """
        def mocked_run_cmdline(request):
            if request['cmd'] == 'payto':
                return {'hex': 'abcd'}
            elif request['cmd'] == 'broadcast':
                return False, 'abcd'

        test_deferred = Deferred()
        wallet = BitcoinWallet(self.session_base_dir)
        mock_daemon = MockObject()
        mock_server = MockObject()
        mock_server.run_cmdline = mocked_run_cmdline
        mock_daemon.get_server = lambda _: mock_server
        wallet.get_daemon = lambda: mock_daemon
        wallet.get_balance = lambda: succeed({'available': 5})

        return wallet.transfer(3, 'abacd').addErrback(lambda _: test_deferred.callback(None))

    @deferred(timeout=10)
    def test_get_transactions(self):
        wallet = BitcoinWallet(self.session_base_dir)
        mock_daemon = MockObject()
        mock_server = MockObject()
        transactions = [{'value': -1, 'txid': 'a', 'timestamp': 1}, {'value': 1, 'txid': 'a', 'timestamp': 1}]
        mock_server.run_cmdline = lambda _: transactions
        mock_daemon.get_server = lambda _: mock_server
        wallet.get_daemon = lambda: mock_daemon
        return wallet.get_transactions()
