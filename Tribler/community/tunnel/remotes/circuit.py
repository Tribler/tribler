import logging
import time

from Tribler.community.tunnel import CIRCUIT_STATE_READY, CIRCUIT_STATE_BROKEN, CIRCUIT_STATE_EXTENDING, \
    CIRCUIT_TYPE_DATA
from Tribler.community.tunnel.remotes.remote_object import RemoteObject, shared
from Tribler.dispersy.candidate import Candidate


class Circuit(RemoteObject):

    """ Circuit data structure storing the id, state and hops """

    def __init__(self, circuit_id, goal_hops=0, first_hop=None, proxy=None,
                 ctype=CIRCUIT_TYPE_DATA, callback=None, required_endpoint=None,
                 mid=None, info_hash=None):
        """
        Instantiate a new Circuit data structure
        :type proxy: TunnelCommunity
        :param int circuit_id: the id of the candidate circuit
        :param (str, int) first_hop: the first hop of the circuit
        :return: Circuit
        """

        assert isinstance(circuit_id, long)
        assert isinstance(goal_hops, int)
        assert first_hop is None or isinstance(first_hop, tuple) and isinstance(
            first_hop[0], basestring) and isinstance(first_hop[1], int)

        self._broken = False
        self.hops = []

        self.circuit_id = circuit_id
        self.first_hop = first_hop
        self.goal_hops = goal_hops
        self.creation_time = time.time()
        self.last_incoming = time.time()
        self.unverified_hop = None
        self.bytes_up = self.bytes_down = 0

        self.proxy = proxy
        self.ctype = ctype
        self.callback = callback
        self.required_endpoint = required_endpoint
        self.mid = mid
        self.hs_session_keys = None
        self.info_hash = info_hash

        self._logger = logging.getLogger(self.__class__.__name__)

    @shared
    def hops(self):
        """
        Return a read only tuple version of the hop-list of this circuit
        @rtype list[<str> hop public key]
        """
        pass

    @shared
    def _broken(self):
        pass

    @shared(True)
    def circuit_id(self):
        pass

    @shared
    def first_hop(self):
        pass

    @shared
    def goal_hops(self):
        pass

    @shared
    def creation_time(self):
        pass

    @shared
    def last_incoming(self):
        pass

    @shared
    def unverified_hop(self):
        pass

    @shared
    def bytes_up(self):
        pass

    @shared
    def bytes_down(self):
        pass

    @shared
    def ctype(self):
        pass

    @shared
    def required_endpoint(self):
        pass

    @shared
    def mid(self):
        pass

    @shared
    def info_hash(self):
        pass

    def add_hop(self, hop):
        """
        Adds a hop to the circuits hop collection
        @param str hop public key: the hop to add
        """
        assert isinstance(hop, basestring)
        self.hops = self.hops + [hop]

    @property
    def state(self):
        """
        The circuit state, can be either:
         CIRCUIT_STATE_BROKEN, CIRCUIT_STATE_EXTENDING or CIRCUIT_STATE_READY
        @rtype: str
        """
        if self._broken:
            return CIRCUIT_STATE_BROKEN

        if len(self.hops) < self.goal_hops:
            return CIRCUIT_STATE_EXTENDING
        else:
            return CIRCUIT_STATE_READY

    def beat_heart(self):
        """
        Mark the circuit as active
        """
        self.last_incoming = time.time()

    def tunnel_data(self, destination, payload):
        """
        Convenience method to tunnel data over this circuit
        @param (str, int) destination: the destination of the packet
        @param str payload: the packet's payload
        """

        self._logger.info("Tunnel data (len %d) to end for circuit %s with ultimate destination %s", len(payload),
                          self.circuit_id, destination)

        num_bytes = self.proxy.send_data([Candidate(tuple(self.first_hop), False)], self.circuit_id,
                                         destination, ('0.0.0.0', 0), payload)
        self.proxy.increase_bytes_sent(self, num_bytes)

        if num_bytes == 0:
            self._logger.warning("Should send %d bytes over circuit %s, zero bytes were sent",
                                 len(payload), self.circuit_id)

    def destroy(self, reason='unknown'):
        """
        Destroys the circuit and calls the error callback of the circuit's
        deferred if it has not been called before

        @param str reason: the reason why the circuit is being destroyed
        """
        self._broken = True

        if self.proxy:
            for hop_id in filter(set(self.hops).__contains__, self.proxy.hops.keys()):
                self.proxy.hops.pop(hop_id)
