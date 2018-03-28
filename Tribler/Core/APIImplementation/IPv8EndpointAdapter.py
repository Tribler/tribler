import socket
from time import time

from Tribler.pyipv8.ipv8.messaging.interfaces.endpoint import Endpoint


class IPv8EndpointAdapter(Endpoint):
    """
    Wrap a Dispersy MIMEndpoint as an IPv8 Endpoint
    """

    def __init__(self, mimep):
        super(IPv8EndpointAdapter, self).__init__()
        mimep.mim = self
        self.endpoint = mimep
        self._is_open = False
        self._prefixes = []

    def add_listener(self, listener):
        super(IPv8EndpointAdapter, self).add_listener(listener)
        if hasattr(listener, "_prefix") and listener.__class_.__name__ != "DiscoveryCommunity":
            self._prefixes.append(listener._prefix)

    def close(self, timeout=0.0):
        """
        Stop the Endpoint. Because we are wrapping a Dispersy endpoint, this does nothing.
        Otherwise, Dispersy would error out.

        The proper way of closing the wrapped endpoint would be:
          self.endpoint.close(timeout)
        """
        pass

    @property
    def _port(self):
        return self.endpoint._port

    def assert_open(self):
        assert self._is_open

    def is_open(self):
        return True

    def open(self, dispersy=None):
        self._is_open = self.endpoint.open(dispersy)

    def send(self, socket_address, packet):
        try:
            self.endpoint._socket.sendto(packet, socket_address)
        except socket.error:
            with self.endpoint._sendqueue_lock:
                did_have_senqueue = bool(self.endpoint._sendqueue)
                self.endpoint._sendqueue.append((time(), socket_address, packet))
            if not did_have_senqueue:
                self.endpoint._process_sendqueue()

    def get_address(self):
        return (self.endpoint._ip, self.endpoint._port)

    def data_came_in(self, packets):
        for packet in packets:
            self.notify_listeners(packet)
        if packets:
            _, data = packets[0]
            return any([data.startswith(prefix) for prefix in self._prefixes])
