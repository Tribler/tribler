from Queue import Queue, Full
from threading import Thread
import logging

from Tribler.dispersy.endpoint import RawserverEndpoint

logger = logging.getLogger(__name__)

__author__ = 'chris'

class HackyEndpoint(RawserverEndpoint):

    def __init__(self, rawserver, port, ip="0.0.0.0"):
        RawserverEndpoint.__init__(self, rawserver, port, ip)
        self.bypass_community = None
        self.bypass_prefix = None
        self.queue = Queue(maxsize=1024)

        self.consumer_thread = Thread(target=self.consumer)
        self.consumer_thread.start()

    def close(self, timeout=0.0):
        self.queue.put_nowait(None)
        RawserverEndpoint.close(self, timeout)

    def consumer(self):
        while True:
            item = self.queue.get()

            if item is None:
                break

            self.bypass_community.on_bypass_message(*item)
            self.queue.task_done()

    def data_came_in(self, packets):
        if self.bypass_prefix and not self.bypass_community:
            raise ValueError("Bypass_community must be set if bypass_prefix is set!")

        # Inspect packages
        normal_packets = []
        try:
            for packet in packets:
                if self.bypass_prefix and packet[1].startswith(self.bypass_prefix):
                    self.queue.put_nowait(packet)

                else:
                    normal_packets.append(packet)
        except Full:
                logger.warning("HackyEndpoint cant keep up with incoming packets, queue is full!")

        RawserverEndpoint.data_came_in(self, normal_packets)

    def send(self, candidates, packets):
        for c in candidates:
            for p in packets:
                try:
                    self._socket.sendto(p, c.sock_addr)
                except IOError:
                    logger.exception("Error writing to socket!")