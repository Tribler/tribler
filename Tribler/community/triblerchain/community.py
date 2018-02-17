from twisted.internet import reactor

from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.community.triblerchain.database import TriblerChainDB
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread

MIN_TRANSACTION_SIZE = 1024 * 1024


class PendingBytes(object):
    def __init__(self, up, down, clean=None):
        super(PendingBytes, self).__init__()
        self.up = up
        self.down = down
        self.clean = clean

    def add(self, up, down):
        if self.up + up >= 0 and self.down + down >= 0:
            self.up = max(0, self.up + up)
            self.down = max(0, self.down + down)
            if self.clean is not None:
                self.clean.reset(2 * 60)
            return True
        else:
            return False


class TriblerChainCommunity(TrustChainCommunity):
    """
    Community for reputation based on TrustChain tamper proof interaction history.
    """
    BLOCK_CLASS = TriblerChainBlock
    DB_CLASS = TriblerChainDB
    SIGN_DELAY = 5
    master_peer = Peer("3081a7301006072a8648ce3d020106052b81040027038192000405c66d3deddb1721787a247b2285118c06ce9fb"
                       "20ebd3546969fa2f4811fa92426637423d3bac1510f92b33e2ff5a785bf54eb3b28d29a77d557011d7d5241243c"
                       "9c89c987cd049404c4024999e1505fa96e1d6668234bde28a666d458d67251d17ff45185515a28967ddcf50503c"
                       "304750ae114f9bc857a79c03da1a9c9215ea07c91f166f24b6cfd1cf72309044fbd".decode('hex'))

    def __init__(self, *args, **kwargs):
        self.tribler_session = kwargs.pop('tribler_session', None)
        super(TriblerChainCommunity, self).__init__(*args, **kwargs)
        self.notifier = None

        if self.tribler_session:
            self.notifier = self.tribler_session.notifier
            self.notifier.add_observer(self.on_tunnel_remove, NTFY_TUNNEL, [NTFY_REMOVE])

        # We store the bytes send and received in the tunnel community in a dictionary.
        # The key is the public key of the peer being interacted with, the value a tuple of the up and down bytes
        # This data is not used to create outgoing requests, but _only_ to verify incoming requests
        self.pending_bytes = dict()

    @blocking_call_on_reactor_thread
    def get_statistics(self, public_key=None):
        """
        Returns a dictionary with some statistics regarding the local trustchain database
        :returns a dictionary with statistics
        """
        if public_key is None:
            public_key = self.my_peer.public_key.key_to_bin()
        latest_block = self.persistence.get_latest(public_key)
        statistics = dict()
        statistics["id"] = public_key.encode("hex")
        interacts = self.persistence.get_num_unique_interactors(public_key)
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

    def on_tunnel_remove(self, subject, change_type, tunnel, sock_addr):
        """
        Handler for the remove event of a tunnel. This function will attempt to create a block for the amounts that
        were transferred using the tunnel.
        :param subject: Category of the notifier event
        :param change_type: Type of the notifier event
        :param tunnel: The tunnel that was removed (closed)
        :param sock_addr: The address of the peer with whom this node has interacted in the tunnel
        """
        tunnel_peer = None
        for verified_peer in self.tribler_session.lm.tunnel_community.network.verified_peers:
            if verified_peer.address == sock_addr:
                tunnel_peer = verified_peer
                break

        if not tunnel_peer:
            self.logger.warning("Could not find interacting peer for signing a TriblerChain block!")
            return

        up = tunnel.bytes_up
        down = tunnel.bytes_down
        pk = tunnel_peer.public_key.key_to_bin()

        # If the transaction is not big enough we discard the bytes up and down.
        if up + down >= MIN_TRANSACTION_SIZE:
            # Tie breaker to prevent both parties from requesting
            if up > down or (up == down and self.my_peer.public_key.key_to_bin() > pk):
                self.register_task("sign_%s" % tunnel.circuit_id,
                                   reactor.callLater(self.SIGN_DELAY, self.sign_block, tunnel_peer, pk,
                                                     {'up': tunnel.bytes_up, 'down': tunnel.bytes_down}))
            else:
                pend = self.pending_bytes.get(pk)
                if not pend:
                    task = self.register_task("cleanup_pending_%s" % tunnel.circuit_id,
                                              reactor.callLater(2 * 60, self.cleanup_pending, pk))
                    self.pending_bytes[pk] = PendingBytes(up, down, task)
                else:
                    pend.add(up, down)

    def cleanup_pending(self, public_key):
        self.pending_bytes.pop(public_key, None)

    def unload(self):
        if self.notifier:
            self.notifier.remove_observer(self.on_tunnel_remove)
        for pk in self.pending_bytes:
            if self.pending_bytes[pk].clean is not None:
                self.pending_bytes[pk].clean.reset(0)
        super(TriblerChainCommunity, self).unload()

    def get_bandwidth_tokens(self, peer=None):
        """
        Get the bandwidth tokens for another peer.
        Currently this is just the difference in the amount of MBs exchanged with them.

        :param member: the peer we interacted with
        :type member: Peer
        :return: the amount of bandwidth tokens for this peer
        :rtype: int
        """
        if peer is None:
            peer = self.my_peer

        block = self.persistence.get_latest(peer.public_key.key_to_bin())
        if block:
            return block.transaction['total_up'] - block.transaction['total_down']

        return 0

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
            'up': 0, 'down': amount
        }

        # Create the two half blocks that form the transaction
        local_half_block = TriblerChainBlock.create(transaction, self.persistence, self.my_peer.public_key.key_to_bin(),
                                                    link_pk=tmp_peer.public_key.key_to_bin())
        local_half_block.sign(self.my_peer.key)
        tmp_half_block = TriblerChainBlock.create(transaction, self.persistence, tmp_peer.public_key.key_to_bin(),
                                                  link=local_half_block, link_pk=self.my_peer.public_key.key_to_bin())
        tmp_half_block.sign(tmp_peer.key)

        self.persistence.add_block(local_half_block)
        self.persistence.add_block(tmp_half_block)

        # Create the bootstrapped identity format
        block = {'block_hash': tmp_half_block.hash.encode('base64'),
                 'sequence_number': tmp_half_block.sequence_number}

        result = {'private_key': tmp_peer.key.key_to_bin().encode('base64'),
                  'transaction': {'up': amount, 'down': 0}, 'block': block}
        return result
