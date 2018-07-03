import imp
import os
import sys
from threading import Thread

import keyring
from Tribler.Core.Modules.wallet.wallet import InsufficientFunds, Wallet
from Tribler.Core.Utilities.install_dir import get_base_path
from jsonrpclib import ProtocolError
from keyring.errors import InitError
from twisted.internet.defer import Deferred, succeed, fail, inlineCallbacks
from twisted.internet.task import LoopingCall

# Make sure we can find the electrum wallet
sys.path.append(os.path.join(get_base_path(), 'electrum'))

imp.load_module('electrum', *imp.find_module('lib'))

from electrum import bitcoin, network
from electrum import SimpleConfig
from electrum import WalletStorage
from electrum.mnemonic import Mnemonic
from electrum.util import InvalidPassword
from electrum import keystore
from electrum import Wallet as ElectrumWallet


class BitcoinWallet(Wallet):
    """
    This class is responsible for handling your wallet of bitcoins.
    """
    TESTNET = False

    def __init__(self, wallet_dir):
        super(BitcoinWallet, self).__init__()

        if self.TESTNET:
            bitcoin.set_testnet()
            network.set_testnet()

        self.wallet_dir = wallet_dir
        self.wallet_file = 'tbtc_wallet' if self.TESTNET else 'btc_wallet'
        self.min_confirmations = 0
        self.daemon = None
        self.wallet_password = None
        self.storage = None
        self.wallet = None

        self.initialize_storage(self.wallet_dir, self.wallet_file)
        if self.created:
            # If the wallet has been created already, we try to unlock it.
            self.unlock_wallet()

    def initialize_storage(self, wallet_dir, wallet_file):
        """
        This will initialize the storage for the BTC wallet.
        """
        self.wallet_dir = wallet_dir
        self.wallet_file = wallet_file

        config = SimpleConfig(options={'cwd': self.wallet_dir, 'wallet_path': self.wallet_file})
        self.storage = WalletStorage(config.get_wallet_path())
        if os.path.exists(config.get_wallet_path()):
            self.created = True

    def unlock_wallet(self):
        """
        Attempt to unlock the BTC wallet with the password in the keychain.
        """
        if not self.created or self.unlocked:
            # Wallet has not been created or unlocked already, do nothing.
            return False

        if self.storage.is_encrypted():
            try:
                keychain_pw = self.get_wallet_password()
                self.wallet_password = keychain_pw if keychain_pw else None  # Convert empty passwords to None
                self.storage.decrypt(self.wallet_password)
                self.unlocked = True
            except InvalidPassword:
                self._logger.error("Invalid BTC wallet password, unable to unlock the wallet!")
            except InitError:
                self._logger.error("Cannot initialize the keychain, unable to unlock the wallet!")
        else:
            # No need to unlock the wallet
            self.unlocked = True

        if self.unlocked:
            config = SimpleConfig(options={'cwd': self.wallet_dir, 'wallet_path': self.wallet_file})
            if os.path.exists(config.get_wallet_path()):
                self.wallet = ElectrumWallet(self.storage)

            self.start_daemon()
            self.open_wallet()
            return True

        return False

    def get_wallet_password(self):
        return keyring.get_password('tribler', 'btc_wallet_password')

    def set_wallet_password(self, password):
        keyring.set_password('tribler', 'btc_wallet_password', password)

    def get_daemon(self):
        """
        Return the daemon that can be used to send JSON RPC commands to. This method is here so we can unit test
        this class.
        """
        from electrum import daemon
        return daemon

    def start_daemon(self):
        options = {'verbose': False, 'cmd': 'daemon', 'testnet': self.TESTNET, 'oneserver': False, 'segwit': False,
                   'cwd': self.wallet_dir, 'portable': False, 'password': '',
                   'wallet_path': os.path.join('wallet', self.wallet_file)}
        if self.TESTNET:
            options['server'] = 'electrum.akinbo.org:51002:s'
        config = SimpleConfig(options)
        fd, _ = self.get_daemon().get_fd_or_server(config)

        if not fd:
            return

        self.daemon = self.get_daemon().Daemon(config, fd, is_gui=False)
        self.daemon.start()

    def open_wallet(self):
        options = {'password': self.wallet_password, 'subcommand': 'load_wallet', 'verbose': False,
                   'cmd': 'daemon', 'testnet': self.TESTNET, 'oneserver': False, 'segwit': False,
                   'cwd': self.wallet_dir, 'portable': False, 'wallet_path': self.wallet_file}
        config = SimpleConfig(options)

        server = self.get_daemon().get_server(config)
        if server is not None:
            # Run the command to open the wallet
            server.daemon(options)

    def get_name(self):
        return 'Bitcoin'

    def get_identifier(self):
        return 'BTC'

    def create_wallet(self, password=''):
        """
        Create a new bitcoin wallet.
        """
        self._logger.info("Creating wallet in %s", self.wallet_dir)

        if password is not None:
            try:
                self.set_wallet_password(password)
            except InitError:
                return fail(RuntimeError("Cannot initialize the keychain, unable to unlock the wallet!"))
        self.wallet_password = password

        def run_on_thread(thread_method):
            # We are running code that writes to the wallet on a separate thread.
            # This is done because Electrum does not allow writing to a wallet from a daemon thread.
            wallet_thread = Thread(target=thread_method, name="ethereum-create-wallet")
            wallet_thread.setDaemon(False)
            wallet_thread.start()
            wallet_thread.join()

        seed = Mnemonic('en').make_seed()
        k = keystore.from_seed(seed, '')
        k.update_password(None, password)
        self.storage.put('keystore', k.dump())
        self.storage.put('wallet_type', 'standard')
        self.storage.set_password(password, bool(password))
        run_on_thread(self.storage.write)

        self.wallet = ElectrumWallet(self.storage)
        self.wallet.synchronize()
        run_on_thread(self.wallet.storage.write)
        self.created = True
        self.unlocked = True

        self.start_daemon()
        self.open_wallet()

        self._logger.info("Bitcoin wallet saved in '%s'", self.wallet.storage.path)

        return succeed(None)

    def get_balance(self):
        """
        Return the balance of the wallet.
        """
        if self.created and self.unlocked:
            options = {'nolnet': False, 'password': None, 'verbose': False, 'cmd': 'getbalance',
                       'wallet_path': self.wallet_file, 'testnet': self.TESTNET, 'segwit': False,
                       'cwd': self.wallet_dir,
                       'portable': False}
            config = SimpleConfig(options)

            server = self.get_daemon().get_server(config)
            result = server.run_cmdline(options)

            confirmed = float(result['confirmed'])
            unconfirmed = float(result['unconfirmed']) if 'unconfirmed' in result else 0
            unconfirmed += (float(result['unmatured']) if 'unmatured' in result else 0)

            return succeed({
                "available": confirmed,
                "pending": unconfirmed,
                "currency": 'BTC',
                "precision": self.precision()
            })

        return succeed({"available": 0, "pending": 0, "currency": 'BTC', "precision": self.precision()})

    def transfer(self, amount, address):
        def on_balance(balance):
            self._logger.info("Creating Bitcoin payment with amount %f to address %s", amount, address)
            if balance['available'] >= amount:
                options = {'password': self.wallet_password, 'verbose': False, 'nocheck': False,
                           'cmd': 'payto', 'wallet_path': self.wallet_file, 'destination': address,
                           'cwd': self.wallet_dir, 'testnet': self.TESTNET, 'rbf': False, 'amount': amount,
                           'segwit': False, 'unsigned': False, 'portable': False}
                config = SimpleConfig(options)

                server = self.get_daemon().get_server(config)
                result = server.run_cmdline(options)
                transaction_hex = result['hex']

                # Broadcast this transaction
                options = {'password': None, 'verbose': False, 'tx': transaction_hex, 'cmd': 'broadcast',
                           'testnet': self.TESTNET, 'timeout': 30, 'segwit': False, 'cwd': self.wallet_dir,
                           'portable': False}
                config = SimpleConfig(options)

                server = self.get_daemon().get_server(config)
                result = server.run_cmdline(options)

                if not result[0]:  # Transaction failed
                    return fail(RuntimeError(result[1]))

                return succeed(str(result[1]))
            else:
                return fail(InsufficientFunds())

        return self.get_balance().addCallback(on_balance)

    def monitor_transaction(self, txid):
        """
        Monitor a given transaction ID. Returns a Deferred that fires when the transaction is present.
        """
        monitor_deferred = Deferred()

        @inlineCallbacks
        def monitor_loop():
            transactions = yield self.get_transactions()
            for transaction in transactions:
                if transaction['id'] == txid:
                    self._logger.debug("Found transaction with id %s", txid)
                    monitor_deferred.callback(None)
                    monitor_lc.stop()

        self._logger.debug("Start polling for transaction %s", txid)
        monitor_lc = self.register_task("btc_poll_%s" % txid, LoopingCall(monitor_loop))
        monitor_lc.start(1)

        return monitor_deferred

    def get_address(self):
        if not self.created or not self.unlocked:
            return ''
        return str(self.wallet.get_receiving_address())

    def get_transactions(self):
        if not self.created or not self.unlocked:
            return succeed([])

        options = {'nolnet': False, 'password': None, 'verbose': False, 'cmd': 'history',
                   'wallet_path': self.wallet_file, 'testnet': self.TESTNET, 'segwit': False, 'cwd': self.wallet_dir,
                   'portable': False}
        config = SimpleConfig(options)

        server = self.get_daemon().get_server(config)
        try:
            result = server.run_cmdline(options)
        except ProtocolError:
            self._logger.error("Unable to fetch transactions from BTC wallet!")
            return succeed([])

        transactions = []
        for transaction in result:
            outgoing = transaction['value'] < 0
            from_address = ','.join(transaction['input_addresses'])
            to_address = ','.join(transaction['output_addresses'])

            transactions.append({
                'id': transaction['txid'],
                'outgoing': outgoing,
                'from': from_address,
                'to': to_address,
                'amount': abs(transaction['value']),
                'fee_amount': 0.0,
                'currency': 'BTC',
                'timestamp': str(transaction['timestamp']),
                'description': 'Confirmations: %d' % transaction['confirmations']
            })

        return succeed(transactions)

    def min_unit(self):
        return 100000  # The minimum amount of BTC we can transfer in this market is mBTC (100000 Satoshi)

    def precision(self):
        return 8


class BitcoinTestnetWallet(BitcoinWallet):
    """
    This wallet represents testnet Bitcoin.
    """
    TESTNET = True

    def get_name(self):
        return 'Testnet BTC'

    def get_identifier(self):
        return 'TBTC'
