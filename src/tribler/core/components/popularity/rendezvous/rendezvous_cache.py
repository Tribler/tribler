import threading
from collections import defaultdict
from time import time

from ipv8.peer import Peer

EMPTY_PEER_CHALLENGE = b'0' * 16
RENDEZVOUS_TIMEOUT = 60


class RendezvousCache:

    def __init__(self):
        self._cache = {}
        self._rendezvous_lock = threading.Lock()

    def add_peer(self, peer, peer_challenge=EMPTY_PEER_CHALLENGE):
        with self._rendezvous_lock:
            self._cache[peer] = (peer_challenge, time())

    def get_rendezvous_peers(self):
        return self._cache.keys()

    def get_rendezvous_challenge(self, peer):
        return self._cache[peer][0]

    def set_rendezvous_challenge(self, peer, challenge):
        return self.add_peer(peer, challenge)

    def clear_inactive_peers(self, timeout=RENDEZVOUS_TIMEOUT):
        with self._rendezvous_lock:
            to_remove = []
            for peer, (peer_challenge, timestamp) in self._cache.items():
                if time() - timestamp > timeout:
                    to_remove.append(peer)
            [self._cache.pop(peer) for peer in to_remove]

    def clear_peer_challenge(self, peer):
        with self._rendezvous_lock:
            self._cache[peer] = (EMPTY_PEER_CHALLENGE, time())
