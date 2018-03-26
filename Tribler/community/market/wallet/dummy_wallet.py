import string
from random import choice

from twisted.internet import reactor
from twisted.internet.defer import succeed
from twisted.internet.task import deferLater

from Tribler.community.market.wallet.wallet import Wallet, InsufficientFunds


class BaseDummyWallet(Wallet):
    """
    This is a dummy wallet that is primarily used for testing purposes
    """
    MONITOR_DELAY = 1

    def __init__(self):
        super(BaseDummyWallet, self).__init__()

        self.balance = 1000
        self.created = True
        self.unlocked = True
        self.address = ''.join([choice(string.lowercase) for _ in xrange(10)])
        self.transaction_history = []

    def get_name(self):
        return 'Dummy'

    def get_identifier(self):
        return 'DUM'

    def create_wallet(self, *args, **kwargs):
        return succeed(None)

    def get_balance(self):
        return succeed({'available': self.balance, 'pending': 0, 'currency': self.get_identifier()})

    def transfer(self, quantity, candidate):
        def on_balance(balance):
            if balance['available'] < quantity:
                raise InsufficientFunds()

            self.balance -= quantity

            self.transaction_history.append({
                'id': str(quantity),
                'outgoing': True,
                'from': self.address,
                'to': '',
                'amount': quantity,
                'fee_amount': 0.0,
                'currency': self.get_identifier(),
                'timestamp': '',
                'description': ''
            })

            return succeed(str(quantity))

        return self.get_balance().addCallback(on_balance)

    def monitor_transaction(self, transaction_id):
        """
        Monitor an incoming transaction with a specific ID.
        """
        def on_transaction_done():
            self.transaction_history.append({
                'id': transaction_id,
                'outgoing': True,
                'from': '',
                'to': self.address,
                'amount': float(str(transaction_id)),
                'fee_amount': 0.0,
                'currency': self.get_identifier(),
                'timestamp': '',
                'description': ''
            })

            self.balance += float(str(transaction_id))  # txid = amount of money transferred

        if self.MONITOR_DELAY == 0:
            return succeed(None).addCallback(lambda _: on_transaction_done())
        else:
            return deferLater(reactor, self.MONITOR_DELAY, on_transaction_done)

    def get_address(self):
        return self.address

    def get_transactions(self):
        return succeed(self.transaction_history)

    def min_unit(self):
        return 1


class DummyWallet1(BaseDummyWallet):

    def get_name(self):
        return 'Dummy 1'

    def get_identifier(self):
        return 'DUM1'


class DummyWallet2(BaseDummyWallet):

    def get_name(self):
        return 'Dummy 2'

    def get_identifier(self):
        return 'DUM2'
