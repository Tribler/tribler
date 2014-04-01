"""
Contains the DispersyBypassEndpoint to be used as Dispersy endpoint when the
ProxyCommunity is being used
"""


from Queue import Queue, Full
from threading import Thread
from Tribler.dispersy.endpoint import RawserverEndpoint
import logging
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
        RawserverEndpoint.__init__(self, raw_server, port, ip)
        self.packet_handlers = {}
        self.queue = Queue()

        self._logger = logging.getLogger(__name__)

    def listen_to(self, prefix, handler):
        """
        Register a prefix to a handler

        @param str prefix: the prefix of a packet to register to the handler
        @param ((str, int), str) -> None handler: the handler that will be
        called for packets starting with the set prefix
        """
        self.packet_handlers[prefix] = handler

    def data_came_in(self, packets):
        """
        Called by the RawServer when UDP packets arrive
        @type packets: list[((str, int), str)]
        @return:
        """
        normal_packets = []
        try:
            for packet in packets:

                prefix = next((p for p in self.packet_handlers if
                               packet[1].startswith(p)), None)
                if prefix:
                    self.packet_handlers[prefix](packet[0], packet[1])
                    # self.queue.put_nowait((prefix, packet))
                else:
                    normal_packets.append(packet)
        except Full:
            self._logger.warning(
                "DispersyBypassEndpoint cant keep up with incoming packets!")

        if normal_packets:
            RawserverEndpoint.data_came_in(self, normal_packets)

    def send_simple(self, candidate, packet):
        self._socket.sendto(packet, candidate.sock_addr)
        return True