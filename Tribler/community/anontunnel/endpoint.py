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

        self.consumer_thread = Thread(target=self.__consumer)
        self.consumer_thread.start()
        self._logger = logging.getLogger(__name__)


    def listen_to(self, prefix, handler):
        """
        Register a prefix to a handler

        @param str prefix: the prefix of a packet to register to the handler
        @param ((str, int), str) -> unknown handler: the handler that will be
        called for packets starting with the set prefix
        """
        self.packet_handlers[prefix] = handler

    def close(self, timeout=0.0):
        """
        Close the endpoint and stops the consumer thread after it processed the
        message queue

        @type timeout: float
        """
        self.queue.put_nowait(None)
        return RawserverEndpoint.close(self, timeout)

    def __consumer(self):
        while True:
            item = self.queue.get()

            if item is None:
                break

            prefix, packet = item
            if prefix in self.packet_handlers:
                self.packet_handlers[prefix](*packet)

            self.queue.task_done()

    def data_came_in(self, packets):
        """
        Called by the RawServer when UDP packets arrive
        @type packets: list[((str, int), str)]
        @return:
        """
        normal_packets = []
        try:
            for packet in packets:

                prefix = next((p for p in self.packet_handlers.keys() if
                               packet[1].startswith(p)), None)
                if prefix:
                    self.queue.put_nowait((prefix, packet))
                else:
                    normal_packets.append(packet)
        except Full:
            self._logger.warning(
                "DispersyBypassEndpoint cant keep up with incoming packets!")

        RawserverEndpoint.data_came_in(self, normal_packets)

    def send(self, candidates, packets):
        """
        Send packets to the specified candidates
        @type candidates: tuple[Candidate] or list[Candidate]
        @type packets: list[str]
        @return:
        """
        for c in candidates:
            for p in packets:
                try:
                    self._socket.sendto(p, c.sock_addr)
                except IOError:
                    self._logger.exception("Error writing to socket!")

        return True