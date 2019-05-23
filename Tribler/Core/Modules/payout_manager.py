from __future__ import absolute_import

import logging
from binascii import hexlify

from ipv8.util import addCallback

from Tribler.Core.Modules.wallet.tc_wallet import TrustchainWallet


class PayoutManager(object):
    """
    This manager is responsible for keeping track of known Tribler peers and doing (zero-hop) payouts.
    """

    def __init__(self, trustchain, dht):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bandwidth_wallet = TrustchainWallet(trustchain)
        self.dht = dht
        self.tribler_peers = {}

    def do_payout(self, mid):
        """
        Perform a payout to a given mid. First, determine the outstanding balance. Then resolve the node in the DHT.
        """
        if mid not in self.tribler_peers:
            return

        total_bytes = sum(self.tribler_peers[mid].values())

        def on_nodes(nodes):
            self.logger.debug("Received %d nodes for DHT lookup", len(nodes))
            if nodes:
                deferred = self.bandwidth_wallet.trustchain.sign_block(nodes[0],
                                                                       public_key=nodes[0].public_key.key_to_bin(),
                                                                       block_type='tribler_bandwidth',
                                                                       transaction={'up': 0, 'down': total_bytes})
                addCallback(deferred, lambda _: None)

        if total_bytes >= 1024 * 1024:  # Do at least 1MB payouts
            self.logger.info("Doing direct payout to %s (%d bytes)", hexlify(mid), total_bytes)
            self.dht.connect_peer(mid).addCallbacks(on_nodes, lambda _: on_nodes([]))

        # Remove the outstanding bytes; otherwise we will payout again
        self.tribler_peers.pop(mid, None)

    def update_peer(self, mid, infohash, balance):
        """
        Update a peer with a specific mid for a specific infohash.
        """
        self.logger.debug("Updating peer with mid %s and ih %s (balance: %d)", hexlify(mid),
                          hexlify(infohash), balance)

        if mid not in self.tribler_peers:
            self.tribler_peers[mid] = {}

        self.tribler_peers[mid][infohash] = balance
