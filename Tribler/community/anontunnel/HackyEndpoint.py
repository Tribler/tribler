from time import time
import logging.config

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
        assert self._dispersy, "Should not be called before open(...)"

        if self.bypass_prefix and not self.bypass_community:
            raise ValueError("Bypass_community must be set if bypass_prefix is set!")

        # Inspect packages
        normal_packets = []
        for packet in packets:
            if self.bypass_prefix and packet[1].startswith(self.bypass_prefix):
                self.bypass_community.on_bypass_message(packet[0], packet[1])
            else:
                normal_packets.append(packet)

        if normal_packets:
            self._dispersy.callback.register(self.dispersythread_data_came_in, (normal_packets, time()))

    def send(self, candidates, packets):
        assert self._dispersy, "Should not be called before open(...)"
        assert isinstance(candidates, (tuple, list, set)), type(candidates)
        assert all(isinstance(candidate, Candidate) for candidate in candidates)
        assert isinstance(packets, (tuple, list, set)), type(packets)
        assert all(isinstance(packet, str) for packet in packets)
        assert all(len(packet) > 0 for packet in packets)
        if any(len(packet) > 2**16 - 60 for packet in packets):
            raise RuntimeError("UDP does not support %d byte packets" % len(max(len(packet) for packet in packets)))

        self._total_up += sum(len(data) for data in packets) * len(candidates)
        self._total_send += (len(packets) * len(candidates))

        wan_address = self._dispersy.wan_address

        for candidate in candidates:
            for p in packets:
                self._socket.sendto(p, candidate.get_destination_address(wan_address))

        return