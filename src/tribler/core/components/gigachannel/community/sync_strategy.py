from random import choice

from ipv8.peerdiscovery.discovery import DiscoveryStrategy

TARGET_PEERS_NUMBER = 20


class RemovePeers(DiscoveryStrategy):
    """
    Synchronization strategy for remote query community.

    Remove a random peer, if we have enough peers to walk to.
    """

    def __init__(self, overlay, target_peers_number=TARGET_PEERS_NUMBER):
        super().__init__(overlay)
        self.target_peers_number = target_peers_number

    def take_step(self):
        with self.walk_lock:
            peers = self.overlay.get_peers()
            if peers and len(peers) > self.target_peers_number:
                self.overlay.network.remove_peer(choice(peers))
