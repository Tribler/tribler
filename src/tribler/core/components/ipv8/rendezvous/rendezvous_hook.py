import logging
import time

from ipv8.peerdiscovery.network import Network, PeerObserver
from ipv8.types import Peer
from tribler.core.components.ipv8.rendezvous.db.database import RendezvousDatabase


class RendezvousHook(PeerObserver):

    def __init__(self, rendezvous_db: RendezvousDatabase) -> None:
        self.rendezvous_db = rendezvous_db

    def shutdown(self, network: Network) -> None:
        for peer in network.verified_peers:
            self.on_peer_removed(peer)
        if self.rendezvous_db:
            self.rendezvous_db.shutdown()

    @property
    def current_time(self) -> float:
        return time.time()

    def on_peer_added(self, peer: Peer) -> None:
        pass

    def on_peer_removed(self, peer: Peer) -> None:
        if self.current_time >= peer.creation_time:
            self.rendezvous_db.add(peer, peer.creation_time, self.current_time)
        else:
            logging.exception("%s was first seen in the future! Something is seriously wrong!", peer)
