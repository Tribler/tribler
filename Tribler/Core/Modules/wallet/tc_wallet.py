from base64 import b64encode

from Tribler.Core.Modules.wallet.bandwidth_block import TriblerBandwidthBlock
from Tribler.Core.Modules.wallet.wallet import Wallet, InsufficientFunds
from Tribler.pyipv8.ipv8.attestation.trustchain.listener import BlockListener
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.peer import Peer
from twisted.internet.defer import succeed, fail, Deferred
from twisted.internet.task import LoopingCall


MEGA_DIV = 1024 * 1024
MIN_TRANSACTION_SIZE = 1024 * 1024


class TrustchainWallet(Wallet, BlockListener):
    """
    This class is responsible for handling your wallet of Tribler tokens.
    """
    MONITOR_DELAY = 1
    BLOCK_CLASS = TriblerBandwidthBlock

    def __init__(self, trustchain):
        super(TrustchainWallet, self).__init__()

        self.trustchain = trustchain
        self.trustchain.add_listener(self, ['tribler_bandwidth'])
        self.created = True
        self.unlocked = True
        self.check_negative_balance = False
        self.transaction_history = []

    def should_sign(self, block):
        """
        Return whether we should sign a given block. For the TrustChain, we only sign a block when we receive bytes.
        In our current design, only the person that should pay bytes to others initiates a signing request.
        This is true when considering payouts in the tunnels and when buying bytes on the market.
        """
        return block.transaction["down"] >= MIN_TRANSACTION_SIZE

    def received_block(self, block):
        pass

    def get_name(self):
        return 'Tokens (MB)'

    def get_identifier(self):
        return 'MB'

    def create_wallet(self, *args, **kwargs):
        raise RuntimeError("You cannot create a Tribler Token wallet")

    def get_bandwidth_tokens(self, peer=None):
        """
        Get the bandwidth tokens for another peer.
        Currently this is just the difference in the amount of MBs exchanged with them.

        :param peer: the peer we interacted with
        :type peer: Peer
        :return: the amount of bandwidth tokens for this peer
        :rtype: int
        """
        if peer is None:
            peer = self.trustchain.my_peer

        block = self.trustchain.persistence.get_latest(peer.public_key.key_to_bin(), block_type='tribler_bandwidth')
        if block:
            return block.transaction['total_up'] - block.transaction['total_down']

        return 0

    def get_balance(self):
        return succeed({
            'available': self.get_bandwidth_tokens() / MEGA_DIV,
            'pending': 0,
            'currency': self.get_identifier(),
            'precision': self.precision()
        })

    def transfer(self, quantity, peer):
        def on_balance(balance):
            if self.check_negative_balance and balance['available'] < quantity:
                return fail(InsufficientFunds())

            return self.create_transfer_block(peer, quantity)

        return self.get_balance().addCallback(on_balance)

    def create_transfer_block(self, peer, quantity):
        transaction = {"up": 0, "down": int(quantity * MEGA_DIV)}
        self.trustchain.sign_block(peer, peer.public_key.key_to_bin(),
                                   block_type='tribler_bandwidth', transaction=transaction)
        latest_block = self.trustchain.persistence.get_latest(self.trustchain.my_peer.public_key.key_to_bin(),
                                                              block_type='tribler_bandwidth')
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

        block = self.trustchain.persistence.get(pub_key, sequence_number)

        monitor_deferred = Deferred()

        def check_has_block():
            self._logger.info("Checking for block with id %s and num %d", pub_key.encode('hex'), sequence_number)
            db_block = self.trustchain.persistence.get(pub_key, sequence_number)
            if db_block:
                monitor_lc.stop()
                monitor_deferred.callback(db_block)

        if block:
            return succeed(block)

        monitor_lc = self.register_task("poll_%s" % payment_id, LoopingCall(check_has_block))
        monitor_lc.start(self.MONITOR_DELAY)
        return monitor_deferred

    def get_address(self):
        return b64encode(self.trustchain.my_peer.public_key.key_to_bin())

    def get_transactions(self):
        return succeed(self.transaction_history)

    def min_unit(self):
        return 1

    def get_num_unique_interactors(self, public_key):
        """
        Returns the number of people you interacted with (either helped or that have helped you)
        :param public_key: The public key of the member of which we want the information
        :return: A tuple of unique number of interactors that helped you and that you have helped respectively
        """
        peers_you_helped = set()
        peers_helped_you = set()
        for block in self.trustchain.persistence.get_latest_blocks(public_key, limit=-1,
                                                                   block_type='tribler_bandwidth'):
            if int(block.transaction["up"]) > 0:
                peers_you_helped.add(block.link_public_key)
            if int(block.transaction["down"]) > 0:
                peers_helped_you.add(block.link_public_key)
        return len(peers_you_helped), len(peers_helped_you)

    def get_statistics(self, public_key=None):
        """
        Returns a dictionary with some statistics regarding the local trustchain database
        :returns a dictionary with statistics
        """
        if public_key is None:
            public_key = self.trustchain.my_peer.public_key.key_to_bin()
        latest_block = self.trustchain.persistence.get_latest(public_key, block_type='tribler_bandwidth')
        statistics = dict()
        statistics["id"] = public_key.encode("hex")
        interacts = self.get_num_unique_interactors(public_key)
        statistics["peers_that_pk_helped"] = interacts[0] if interacts[0] is not None else 0
        statistics["peers_that_helped_pk"] = interacts[1] if interacts[1] is not None else 0
        if latest_block:
            statistics["total_blocks"] = latest_block.sequence_number
            statistics["total_up"] = latest_block.transaction["total_up"]
            statistics["total_down"] = latest_block.transaction["total_down"]
            statistics["latest_block"] = dict(latest_block)

            # Set up/down
            statistics["latest_block"]["up"] = latest_block.transaction["up"]
            statistics["latest_block"]["down"] = latest_block.transaction["down"]
        else:
            statistics["total_blocks"] = 0
            statistics["total_up"] = 0
            statistics["total_down"] = 0
        return statistics

    def bootstrap_new_identity(self, amount):
        """
        One-way payment channel.
        Create a new temporary identity, and transfer funds to the new identity.
        A different party can then take the result and do a transfer from the temporary identity to itself
        """

        # Create new identity for the temporary identity
        crypto = ECCrypto()
        tmp_peer = Peer(crypto.generate_key(u"curve25519"))

        # Create the transaction specification
        transaction = {
            'up': 0,
            'down': amount,
            'type': 'tribler_bandwidth'
        }

        # Create the two half blocks that form the transaction
        local_half_block = TriblerBandwidthBlock.create('tribler_bandwidth', transaction, self.trustchain.persistence,
                                                        self.trustchain.my_peer.public_key.key_to_bin(),
                                                        link_pk=tmp_peer.public_key.key_to_bin())
        local_half_block.sign(self.trustchain.my_peer.key)
        tmp_half_block = TriblerBandwidthBlock.create('tribler_bandwidth', transaction, self.trustchain.persistence,
                                                      tmp_peer.public_key.key_to_bin(),
                                                      link=local_half_block,
                                                      link_pk=self.trustchain.my_peer.public_key.key_to_bin())
        tmp_half_block.sign(tmp_peer.key)

        self.trustchain.persistence.add_block(local_half_block)
        self.trustchain.persistence.add_block(tmp_half_block)

        # Create the bootstrapped identity format
        block = {'block_hash': tmp_half_block.hash.encode('base64'),
                 'sequence_number': tmp_half_block.sequence_number}

        result = {'private_key': tmp_peer.key.key_to_bin().encode('base64'),
                  'transaction': {'up': amount, 'down': 0}, 'block': block}
        return result

    def precision(self):
        return 0
