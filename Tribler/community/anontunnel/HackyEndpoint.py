from time import time
import logging

from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.endpoint import RawserverEndpoint


logger = logging.getLogger(__name__)

__author__ = 'chris'

class HackyEndpoint(RawserverEndpoint):

    def __init__(self, rawserver, port, ip="0.0.0.0"):
        RawserverEndpoint.__init__(self, rawserver, port, ip)
        self.bypass_community = None
        self.bypass_prefix = None

    def data_came_in(self, packets):
        if self.bypass_prefix and not self.bypass_community:
            raise ValueError("Bypass_community must be set if bypass_prefix is set!")

        # Inspect packages
        normal_packets = []
        for packet in packets:
            if self.bypass_prefix and packet[1].startswith(self.bypass_prefix):
                self.bypass_community.on_bypass_message(packet[0], packet[1])
            else:
                normal_packets.append(packet)

        RawserverEndpoint.data_came_in(self, normal_packets)

    def send(self, candidates, packets):
        for c in candidates:
            for p in packets:
                self._socket.sendto(p, c.sock_addr)