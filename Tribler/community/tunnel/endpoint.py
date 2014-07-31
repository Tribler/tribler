"""
Contains the DispersyBypassEndpoint to be used as Dispersy endpoint when the
ProxyCommunity is being used
"""
from Tribler.dispersy.endpoint import RawserverEndpoint, TunnelEndpoint


__author__ = 'chris'


class DispersyBypassEndpoint(RawserverEndpoint):
    """
    Creates an Dispersy Endpoint which bypasses the Dispersy message handling
    system for incoming packets matching set prefixes

    @type raw_server: Tribler.Core.RawServer.RawServer.RawServer
    @type port: int
    @type ip: str
    """
    def __init__(self, raw_server, port, ip="0.0.0.0"):
        super(DispersyBypassEndpoint, self).__init__(raw_server, port, ip)
        self.packet_handlers = {}

    def listen_to(self, prefix, handler):
        """
        Register a prefix to a handler

        @param str prefix: the prefix of a packet to register to the handler
        @param ((str, int), str) -> None handler: the handler that will be
        called for packets starting with the set prefix
        """
        self.packet_handlers[prefix] = handler

    def data_came_in(self, packets, cache=True):
        """
        Called by the RawServer when UDP packets arrive
        @type packets: list[((str, int), str)]
        @return:
        """
        normal_packets = []
        for packet in packets:

            prefix = next((p for p in self.packet_handlers if
                           packet[1].startswith(p)), None)
            if prefix:
                sock_addr, data = packet
                self.packet_handlers[prefix](sock_addr, data[len(prefix):])
            else:
                normal_packets.append(packet)

        if normal_packets:
            super(DispersyBypassEndpoint, self).data_came_in(normal_packets, cache)

    def send(self, candidates, packets, prefix=None):
        prefix = prefix or ''
        super(DispersyBypassEndpoint, self).send(candidates, [prefix + packet for packet in packets])

    def send_packet(self, candidate, packet, prefix=None):
        prefix = prefix or ''
        super(DispersyBypassEndpoint, self).send_packet(candidate, prefix + packet)


class DispersyTunnelBypassEndpoint(TunnelEndpoint):
    def __init__(self, swift_process):
        super(DispersyTunnelBypassEndpoint, self).__init__(swift_process)

    def listen_to(self, prefix, handler):
        """
        Register a prefix to a handler

        @param str prefix: the prefix of a packet to register to the handler
        @param ((str, int), str) -> None handler: the handler that will be
        called for packets starting with the set prefix
        """
        def handler_wrapper(session, sock_addr, data):
            handler(sock_addr, data)
            self._dispersy.statistics.total_down += len(data)

        self._swift.register_tunnel(prefix, handler_wrapper)
