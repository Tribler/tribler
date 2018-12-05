import os

import time

# Important import, do not remove
import Tribler.Core.Modules.bitcoinlib_main as bitcoinlib_main

from Tribler.Core.Modules.wallet.wallet import Wallet, InsufficientFunds
from twisted.internet.defer import Deferred, succeed, inlineCallbacks, fail
from twisted.internet.task import LoopingCall
from twisted.python.failure import Failure


class BitcoinWallet(Wallet):
    """
    This class is responsible for handling your wallet of bitcoins.

    NOTE: all imports of bitcoinlib should be local. The reason for this is that we are patching the bitcoinlib_main
          method in the __init__ method of the class (since we need access to the Tribler state directory) and
          we can only import bitcoinlib *after* patching the bitcoinlib main file.
    """
    TESTNET = False

    def __init__(self, wallet_dir):
        super(BitcoinWallet, self).__init__()

        bitcoinlib_main.initialize_lib(wallet_dir)
        from bitcoinlib.wallets import wallet_exists, HDWallet

        self.network = 'testnet' if self.TESTNET else 'bitcoin'
        self.wallet_dir = wallet_dir
        self.min_confirmations = 0
        self.wallet = None
        self.unlocked = True
        self.db_path = os.path.join(wallet_dir, 'wallets.sqlite')
        self.wallet_name = 'tribler_testnet' if self.TESTNET else 'tribler'

        if wallet_exists(self.wallet_name, databasefile=self.db_path):
            self.wallet = HDWallet(self.wallet_name, databasefile=self.db_path)
            self.created = True

    def get_name(self):
        return 'Bitcoin'

    def get_identifier(self):
        return 'BTC'

    def create_wallet(self):
        """
        Create a new bitcoin wallet.
        """
        from bitcoinlib.wallets import wallet_exists, HDWallet, WalletError

        if wallet_exists(self.wallet_name, databasefile=self.db_path):
            return fail(RuntimeError("Bitcoin wallet with name %s already exists." % self.wallet_name))

        self._logger.info("Creating wallet in %s", self.wallet_dir)
        try:
            self.wallet = HDWallet.create(self.wallet_name, network=self.network, databasefile=self.db_path)
            self.wallet.new_key('tribler_payments')
            self.wallet.new_key('tribler_change', change=1)
            self.created = True
        except WalletError as exc:
            self._logger.error("Cannot create BTC wallet!")
            return fail(Failure(exc))
        return succeed(None)

    def get_balance(self):
        """
        Return the balance of the wallet.
        """
        if self.created:
            self.wallet.utxos_update(networks=self.network)
            return succeed({
                "available": self.wallet.balance(network=self.network),
                "pending": 0,
                "currency": 'BTC',
                "precision": self.precision()
            })

        return succeed({"available": 0, "pending": 0, "currency": 'BTC', "precision": self.precision()})

    def transfer(self, amount, address):
        def on_balance(balance):
            if balance['available'] >= amount:
                self._logger.info("Creating Bitcoin payment with amount %f to address %s", amount, address)
                tx = self.wallet.send_to(address, int(amount))
                return str(tx.hash)
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
        monitor_lc.start(5)

        return monitor_deferred

    def get_address(self):
        if not self.created:
            return ''
        return self.wallet.keys(name='tribler_payments', is_active=False)[0].address

    def get_transactions(self):
        if not self.created:
            return succeed([])

        from bitcoinlib.transactions import Transaction
        from bitcoinlib.wallets import DbTransaction, DbTransactionInput

        # Update all transactions
        self.wallet.transactions_update(network=self.network)

        txs = self.wallet._session.query(DbTransaction.raw, DbTransaction.confirmations,
                                         DbTransaction.date, DbTransaction.fee)\
            .filter(DbTransaction.wallet_id == self.wallet.wallet_id)\
            .all()
        transactions = []

        for db_result in txs:
            transaction = Transaction.import_raw(db_result[0], network=self.network)
            transaction.confirmations = db_result[1]
            transaction.date = db_result[2]
            transaction.fee = db_result[3]
            transactions.append(transaction)

        # Sort them based on locktime
        transactions.sort(key=lambda tx: tx.locktime, reverse=True)

        my_keys = [key.address for key in self.wallet.keys(network=self.network, is_active=False)]

        transactions_list = []
        for transaction in transactions:
            value = 0
            input_addresses = []
            output_addresses = []
            for tx_input in transaction.inputs:
                input_addresses.append(tx_input.address)
                if tx_input.address in my_keys:
                    # At this point, we do not have the value of the input so we should do a database query for it
                    db_res = self.wallet._session.query(DbTransactionInput.value).filter(
                        tx_input.prev_hash.encode('hex') == DbTransactionInput.prev_hash,
                        tx_input.output_n_int == DbTransactionInput.output_n).all()
                    if db_res:
                        value -= db_res[0][0]

            for tx_output in transaction.outputs:
                output_addresses.append(tx_output.address)
                if tx_output.address in my_keys:
                    value += tx_output.value

            transactions_list.append({
                'id': transaction.hash,
                'outgoing': value < 0,
                'from': ','.join(input_addresses),
                'to': ','.join(output_addresses),
                'amount': abs(value),
                'fee_amount': transaction.fee,
                'currency': 'BTC',
                'timestamp': time.mktime(transaction.date.timetuple()),
                'description': 'Confirmations: %d' % transaction.confirmations
            })

        return succeed(transactions_list)

    def min_unit(self):
        return 100000  # The minimum amount of BTC we can transfer in this market is 1 mBTC (100000 Satoshi)

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
