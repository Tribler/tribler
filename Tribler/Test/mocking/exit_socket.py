from __future__ import absolute_import

from Tribler.Test.mocking.endpoint import AutoMockEndpoint
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import TunnelExitSocket, DataChecker
from Tribler.pyipv8.ipv8.messaging.interfaces.endpoint import EndpointListener
from twisted.internet.defer import succeed



class MockTunnelExitSocket(TunnelExitSocket, EndpointListener):

    def __init__(self, parent):
        self.endpoint = AutoMockEndpoint()
        self.endpoint.open()

        TunnelExitSocket.__init__(self, parent.circuit_id, parent.overlay, parent.sock_addr, parent.mid)
        parent.close()
        EndpointListener.__init__(self, self.endpoint)

        self.endpoint.add_listener(self)

    def enable(self):
        pass

    @property
    def enabled(self):
        return True

    def sendto(self, data, destination):
        if DataChecker.is_allowed(data):
            self.endpoint.send(destination, data)
        else:
            raise AssertionError("Attempted to exit data which is not allowed" % repr(data))

    def on_packet(self, packet):
        source_address, data = packet
        self.datagramReceived(data, source_address)

    def close(self):
        return succeed(True)
