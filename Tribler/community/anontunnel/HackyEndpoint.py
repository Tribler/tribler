from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.endpoint import RawserverEndpoint, TUNNEL_PREFIX
from time import time

import logging.config

logger = logging.getLogger(__name__)

__author__ = 'chris'

class HackyEndpoint(RawserverEndpoint):

    def __init__(self, rawserver, port, ip="0.0.0.0"):
        RawserverEndpoint.__init__(self,rawserver,port, ip)
        self.bypass_community = None
        self.bypass_prefix = None

    def data_came_in(self, packets):
        assert self._dispersy, "Should not be called before open(...)"

        normal_packets = [packet for packet in packets if not self.bypass_prefix or not packet[1].startswith(self.bypass_prefix) and not packet[1].startswith(TUNNEL_PREFIX + self.bypass_prefix)]

        if normal_packets:
            self._dispersy.callback.register(self.dispersythread_data_came_in, (normal_packets, time()))

        if not self.bypass_prefix:
            return

        bypass_packets = [
            (data.startswith(TUNNEL_PREFIX), address, data)
            for address, data in packets if data.startswith(self.bypass_prefix) or data.startswith(TUNNEL_PREFIX + self.bypass_prefix)]



        candidate_data_pairs = [(Candidate(sock_addr, tunnel), data[4:] if tunnel else data)
                                        for tunnel, sock_addr, data
                                        in bypass_packets]

        if candidate_data_pairs:
            for candidate, data in candidate_data_pairs:
                candidate = self.bypass_community.candidates.get(candidate.sock_addr) or candidate
                self.bypass_community.on_bypass_message(candidate, packet[1])


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