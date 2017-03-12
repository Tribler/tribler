import time

from Tribler.community.tunnel.remotes.remote_object import RemoteObject, shared

class RelayRoute(RemoteObject):

    """
    Relay object containing the destination circuit, socket address and whether
    it is online or not
    """

    def __init__(self, circuit_id, sock_addr, rendezvous_relay=False, mid=None):
        """
        @type sock_addr: (str, int)
        @type circuit_id: int
        @return:
        """

        self.sock_addr = sock_addr
        self.circuit_id = circuit_id
        self.creation_time = time.time()
        self.last_incoming = time.time()
        self.bytes_up = self.bytes_down = 0
        self.rendezvous_relay = rendezvous_relay
        self.mid = mid

    @shared
    def sock_addr(self):
        pass

    @shared(True)
    def circuit_id(self):
        pass

    @shared
    def creation_time(self):
        pass

    @shared
    def last_incoming(self):
        pass

    @shared
    def bytes_up(self):
        pass

    @shared
    def bytes_down(self):
        pass

    @shared
    def rendezvous_relay(self):
        pass

    @shared
    def mid(self):
        pass
