import logging
import time

from ipv8.peerdiscovery.network import Network, PeerObserver
from ipv8.types import Peer

from tribler.core.rendezvous.database import RendezvousDatabase


class RendezvousHook(PeerObserver):
    """
    Keep track of peers that we have seen.
    """

    def __init__(self, rendezvous_db: RendezvousDatabase) -> None:
        """
        Write rendezvous info to the given database.
        """
        self.rendezvous_db = rendezvous_db

    def shutdown(self, network: Network) -> None:
        """
        Write all data to disk.
        """
        for peer in network.verified_peers:
            self.on_peer_removed(peer)
        if self.rendezvous_db:
            self.rendezvous_db.shutdown()

    @property
    def current_time(self) -> float:
        """
        Get the current time.
        """
        return time.time()

    def on_peer_added(self, peer: Peer) -> None:
        """
        Callback for when a peer comes online. We do nothing with this info.
        """

    def on_peer_removed(self, peer: Peer) -> None:
        """
        Callback for when a peer is removed: write its online time to the database.
        """
        if self.current_time >= peer.creation_time:
            self.rendezvous_db.add(peer, peer.creation_time, self.current_time)
        else:
            logging.exception("%s was first seen in the future! Something is seriously wrong!", peer)
