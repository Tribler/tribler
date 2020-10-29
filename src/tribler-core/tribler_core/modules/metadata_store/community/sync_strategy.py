from random import choice

from ipv8.peerdiscovery.discovery import DiscoveryStrategy


class SyncChannels(DiscoveryStrategy):
    """
    Synchronization strategy for gigachannels.

    On each tick we send a random peer some of our random subscribed channels.
    """

    def take_step(self):
        with self.walk_lock:
            # Share my random channels
            peers = self.overlay.get_peers()
            if peers:
                peer = choice(peers)
                self.overlay.send_random_to(peer)


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
