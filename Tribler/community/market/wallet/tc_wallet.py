from base64 import b64encode

from twisted.internet.defer import succeed, fail, Deferred
from twisted.internet.task import LoopingCall

from Tribler.community.market.wallet.wallet import Wallet, InsufficientFunds


MEGA_DIV = 1024 * 1024


class TrustchainWallet(Wallet):
    """
    This class is responsible for handling your wallet of TrustChain credits.
    """
    MONITOR_DELAY = 1

    def __init__(self, tc_community):
        super(TrustchainWallet, self).__init__()

        self.tc_community = tc_community
        self.created = True
        self.check_negative_balance = True
        self.transaction_history = []

    def get_name(self):
        return 'Reputation'

    def get_identifier(self):
        return 'MC'

    def create_wallet(self, *args, **kwargs):
        raise RuntimeError("You cannot create a TrustChain wallet")

    def get_balance(self):
        latest_block = self.tc_community.persistence.get_latest(self.tc_community.my_peer.public_key.key_to_bin())
        total_up = latest_block.transaction["total_up"] / MEGA_DIV if latest_block else 0
        total_down = latest_block.transaction["total_down"] / MEGA_DIV if latest_block else 0
        return succeed({'available': total_up - total_down, 'pending': 0, 'currency': self.get_identifier()})

    def transfer(self, quantity, peer):
        def on_balance(balance):
            if self.check_negative_balance and balance['available'] < quantity:
                return fail(InsufficientFunds())

            return self.send_signature(peer, quantity)

        return self.get_balance().addCallback(on_balance)

    def send_signature(self, peer, quantity):
        transaction = {"up": 0, "down": int(quantity * MEGA_DIV)}
        self.tc_community.sign_block(peer, peer.public_key.key_to_bin(), transaction)
        latest_block = self.tc_community.persistence.get_latest(self.tc_community.my_peer.public_key.key_to_bin())
        txid = "%s.%s.%d.%d" % (latest_block.public_key.encode('hex'),
                                latest_block.sequence_number, 0, int(quantity * MEGA_DIV))

        self.transaction_history.append({
            'id': txid,
            'outgoing': True,
            'from': self.get_address(),
            'to': b64encode(peer.public_key.key_to_bin()),
            'amount': quantity,
            'fee_amount': 0.0,
            'currency': self.get_identifier(),
            'timestamp': '',
            'description': ''
        })

        return succeed(txid)

    def monitor_transaction(self, payment_id):
        """
        Monitor an incoming transaction with a specific id.
        """
        pub_key, sequence_number = payment_id.split('.')[:2]
        pub_key = pub_key.decode('hex')
        sequence_number = int(sequence_number)

        block = self.tc_community.persistence.get(pub_key, sequence_number)

        monitor_deferred = Deferred()

        def check_has_block():
            self._logger.info("Checking for block with id %s and num %d", pub_key.encode('hex'), sequence_number)
            db_block = self.tc_community.persistence.get(pub_key, sequence_number)
            self._logger.error("BLOCKS: %s", self.tc_community.persistence.get_latest(pub_key))
            if db_block:
                monitor_lc.stop()
                monitor_deferred.callback(db_block)

        if block:
            return succeed(block)

        monitor_lc = LoopingCall(check_has_block)
        monitor_lc.start(self.MONITOR_DELAY)
        return monitor_deferred

    def get_address(self):
        return b64encode(self.tc_community.my_peer.public_key.key_to_bin())

    def get_transactions(self):
        return succeed(self.transaction_history)

    def min_unit(self):
        return 1
