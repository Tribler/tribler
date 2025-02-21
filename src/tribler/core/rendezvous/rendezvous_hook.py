import logging
import time

from ipv8.community import Community
from ipv8.peerdiscovery.network import Network, PeerObserver
from ipv8.types import Peer
from pony.orm import db_session

from tribler.core.rendezvous.database import RendezvousDatabase


class RendezvousHook(PeerObserver):
    """
    Keep track of peers that we have seen.
    """

    def __init__(self, rendezvous_db: RendezvousDatabase, community: Community) -> None:
        """
        Write rendezvous info to the given database.
        """
        self.rendezvous_db = rendezvous_db

        self.write_queue: list[tuple[Peer, float, float]] = []

        self.community = community
        self.community.register_shutdown_task(self.shutdown, community.network)
        self.community.register_task("Peer write scheduler", self.schedule_write_peers, interval=60.0)

    def consume_write_queue(self, queue: list[tuple[Peer, float, float]]) -> None:
        """
        Consume the queue in bulk.
        """
        with db_session:
            for entry in queue:
                self.rendezvous_db.add(*entry)

    async def schedule_write_peers(self) -> None:
        """
        Write the peers in an executor.
        """
        forward = self.write_queue
        self.write_queue = []
        await self.community.register_executor_task("Peer write executor", self.consume_write_queue, forward)

    def shutdown(self, network: Network) -> None:
        """
        Write all data to disk.
        """
        self.consume_write_queue([(peer, peer.creation_time, self.current_time) for peer in network.verified_peers
                                  if self.current_time >= peer.creation_time])
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
            self.write_queue.append((peer, peer.creation_time, self.current_time))
        else:
            logging.exception("%s was first seen in the future! Something is seriously wrong!", peer)
