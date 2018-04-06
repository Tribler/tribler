from Tribler.Core.Modules.wallet.btc_wallet import BitcoinTestnetWallet, BitcoinWallet
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from jsonrpclib import ProtocolError
from twisted.internet.defer import succeed, Deferred


class TestBtcWallet(AbstractServer):

    @deferred(timeout=20)
    def test_btc_wallet(self):
        """
        Test the creating, opening, transactions and balance query of a Bitcoin wallet
        """
        wallet = BitcoinTestnetWallet(self.session_base_dir)

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

            _ = BitcoinTestnetWallet(self.session_base_dir)
            wallet.set_wallet_password('abc')
            self.assertRaises(Exception, BitcoinTestnetWallet, self.session_base_dir, testnet=True)
            self.assertFalse(wallet.unlock_wallet())

            return wallet.get_balance().addCallback(on_wallet_balance)

        return wallet.create_wallet('tribler').addCallback(on_wallet_created)

    def test_btc_wallet_name(self):
        """
        Test the name of a Bitcoin wallet
        """
        wallet = BitcoinTestnetWallet(self.session_base_dir)
        self.assertEqual(wallet.get_name(), 'Testnet BTC')

    def test_btc_wallet_identfier(self):
        """
        Test the identifier of a Bitcoin wallet
        """
        wallet = BitcoinTestnetWallet(self.session_base_dir)
        self.assertEqual(wallet.get_identifier(), 'TBTC')

    def test_btc_wallet_address(self):
        """
        Test the address of a Bitcoin wallet
        """
        wallet = BitcoinTestnetWallet(self.session_base_dir)
        self.assertEqual(wallet.get_address(), '')

    def test_btc_wallet_unit(self):
        """
        Test the mininum unit of a Bitcoin wallet
        """
        wallet = BitcoinTestnetWallet(self.session_base_dir)
        self.assertEqual(wallet.min_unit(), 0.0001)

    def test_btc_balance_no_wallet(self):
        """
        Test the retrieval of the balance of a BTC wallet that is not created yet
        """
        def on_wallet_balance(balance):
            self.assertDictEqual(balance, {'available': 0, 'pending': 0, 'currency': 'BTC'})

        wallet = BitcoinTestnetWallet(self.session_base_dir)
        return wallet.get_balance().addCallback(on_wallet_balance)

    @deferred(timeout=10)
    def test_btc_wallet_transfer_no_funds(self):
        """
        Test that the transfer method of a BTC wallet raises an error when we don't have enough funds
        """
        test_deferred = Deferred()

        wallet = BitcoinTestnetWallet(self.session_base_dir)
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

        wallet = BitcoinTestnetWallet(self.session_base_dir)
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
        wallet = BitcoinTestnetWallet(self.session_base_dir)
        mock_daemon = MockObject()
        mock_server = MockObject()
        mock_server.run_cmdline = mocked_run_cmdline
        mock_daemon.get_server = lambda _: mock_server
        wallet.get_daemon = lambda: mock_daemon
        wallet.get_balance = lambda: succeed({'available': 5})

        return wallet.transfer(3, 'abacd').addErrback(lambda _: test_deferred.callback(None))

    @deferred(timeout=10)
    def test_get_transactions(self):
        wallet = BitcoinTestnetWallet(self.session_base_dir)
        mock_daemon = MockObject()
        mock_server = MockObject()
        transactions = [{
            'value': -1,
            'txid': 'a',
            'timestamp': 1,
            'input_addresses': ['a', 'b'],
            'output_addresses': ['c', 'd'],
            'confirmations': 3
        }, {
            'value': 1,
            'txid': 'b',
            'timestamp': False,  # In Electrum, this means that the transaction has not been confirmed yet
            'input_addresses': ['a', 'b'],
            'output_addresses': ['c', 'd'],
            'confirmations': 0
        }]
        mock_server.run_cmdline = lambda _: transactions
        mock_daemon.get_server = lambda _: mock_server
        wallet.get_daemon = lambda: mock_daemon
        return wallet.get_transactions()

    @deferred(timeout=10)
    def test_get_transactions_error(self):
        """
        Test whether no transactions are returned when there's a protocol in the JSON RPC protocol
        """
        wallet = BitcoinTestnetWallet(self.session_base_dir)
        mock_daemon = MockObject()
        mock_server = MockObject()

        def failing_run_cmdline(*_):
            raise ProtocolError()

        mock_server.run_cmdline = failing_run_cmdline
        mock_daemon.get_server = lambda _: mock_server
        wallet.get_daemon = lambda: mock_daemon

        def verify_transactions(transactions):
            self.assertFalse(transactions)

        return wallet.get_transactions().addCallback(verify_transactions)


class TestBtcTestnetWallet(AbstractServer):

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
