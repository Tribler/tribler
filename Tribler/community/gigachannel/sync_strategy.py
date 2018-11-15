from random import choice

from Tribler.pyipv8.ipv8.peerdiscovery.discovery import DiscoveryStrategy


class SyncChannels(DiscoveryStrategy):
    """
    Synchronization strategy for gigachannels.

    On each tick we:
     1. Send a random peer some of our random subscribed channels.
     2. Check if we have any pending channels to download.
    """

    def take_step(self, service_id=None):
        with self.walk_lock:
            # Share my random channels
            peers = self.overlay.get_peers()
            if peers:
                peer = choice(peers)
                self.overlay.send_random_to(peer)
            # Try to fetch pending channels
            self.overlay.fetch_next()
