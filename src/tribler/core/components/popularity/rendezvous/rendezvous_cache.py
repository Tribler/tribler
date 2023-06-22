import threading
from collections import defaultdict


class RendezvousCache:

    def __init__(self):
        self._cache = defaultdict(bytes)
        self._rendezvous_lock = threading.Lock()

    def __getitem__(self, item):
        with self._rendezvous_lock:
            return self._cache[item]

    def __setitem__(self, key, value):
        with self._rendezvous_lock:
            self._cache[key] = value

    def get_rendezvous_challenge(self, peer_mid):
        return self.__getitem__(peer_mid)

    def set_rendezvous_challenge(self, peer_mid, challenge):
        return self.__setitem__(peer_mid, challenge)
