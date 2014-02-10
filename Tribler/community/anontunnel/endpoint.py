from Queue import Queue, Full
from threading import Thread
import logging

from Tribler.dispersy.endpoint import RawserverEndpoint

logger = logging.getLogger(__name__)

__author__ = 'chris'


class DispersyBypassEndpoint(RawserverEndpoint):

    def __init__(self, rawserver, port, ip="0.0.0.0"):
        RawserverEndpoint.__init__(self, rawserver, port, ip)
        self.packet_handlers = {}
        self.queue = Queue(maxsize=1024)

        self.consumer_thread = Thread(target=self.consumer)
        self.consumer_thread.start()

    def listen_to(self, prefix, handler):
        self.packet_handlers[prefix] = handler

    def close(self, timeout=0.0):
        self.queue.put_nowait(None)
        return RawserverEndpoint.close(self, timeout)

    def consumer(self):
        while True:
            item = self.queue.get()

            if item is None:
                break

            prefix, packet = item
            if prefix in self.packet_handlers:
                self.packet_handlers[prefix](*packet)

            self.queue.task_done()

    def data_came_in(self, packets):
        # Inspect packages
        normal_packets = []
        try:
            for packet in packets:

                prefix = next((p for p in self.packet_handlers.keys() if packet[1].startswith(p)), None)
                if prefix:
                    self.queue.put_nowait((prefix, packet))
                else:
                    normal_packets.append(packet)
        except Full:
                logger.warning("DispersyBypassEndpoint cant keep up with incoming packets, queue is full!")

        RawserverEndpoint.data_came_in(self, normal_packets)

    def send(self, candidates, packets):
        for c in candidates:
            for p in packets:
                try:
                    self._socket.sendto(p, c.sock_addr)
                except IOError:
                    logger.exception("Error writing to socket!")