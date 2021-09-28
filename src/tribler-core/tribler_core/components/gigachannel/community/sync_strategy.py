from random import choice

from ipv8.peerdiscovery.discovery import DiscoveryStrategy


class RemovePeers(DiscoveryStrategy):
    """
    Synchronization strategy for remote query community.

    Remove a random peer, if we have enough peers to walk to.
    """

    def take_step(self):
        with self.walk_lock:
            peers = self.overlay.get_peers()
            if peers and len(peers) > 20:
                self.overlay.network.remove_peer(choice(peers))
