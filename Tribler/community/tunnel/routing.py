import time

from Tribler.community.tunnel import CIRCUIT_STATE_READY, CIRCUIT_STATE_BROKEN, CIRCUIT_STATE_EXTENDING, \
    CIRCUIT_TYPE_DATA
from Tribler.dispersy.crypto import LibNaCLPK
from Tribler.dispersy.candidate import Candidate
import logging

__author__ = 'chris'


class Circuit(object):

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

        from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
        assert isinstance(circuit_id, long)
        assert isinstance(goal_hops, int)
        assert proxy is None or isinstance(proxy, HiddenTunnelCommunity)
        assert first_hop is None or isinstance(first_hop, tuple) and isinstance(
            first_hop[0], basestring) and isinstance(first_hop[1], int)

        self._broken = False
        self._hops = []

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

    @property
    def hops(self):
        """
        Return a read only tuple version of the hop-list of this circuit
        @rtype tuple[Hop]
        """
        return tuple(self._hops)

    def add_hop(self, hop):
        """
        Adds a hop to the circuits hop collection
        @param Hop hop: the hop to add
        """
        self._hops.append(hop)

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
        @return bool: whether the tunnel request has succeeded, this is in no
         way an acknowledgement of delivery!
        """

        self._logger.info("Tunnel data (len %d) to end for circuit %s with ultimate destination %s", len(payload),
                           self.circuit_id, destination)

        num_bytes = self.proxy.send_data([Candidate(self.first_hop, False)], self.circuit_id, destination, ('0.0.0.0', 0), payload)
        self.proxy.increase_bytes_sent(self.circuit_id, num_bytes)

        return num_bytes > 0

    def destroy(self, reason='unknown'):
        """
        Destroys the circuit and calls the error callback of the circuit's
        deferred if it has not been called before

        @param str reason: the reason why the circuit is being destroyed
        """
        self._broken = True


class Hop(object):

    """
    Circuit Hop containing the address, its public key and the first part of
    the Diffie-Hellman handshake
    """

    def __init__(self, public_key=None):
        """
        @param None|LibNaCLPK public_key: public key object of the hop
        """

        assert public_key is None or isinstance(public_key, LibNaCLPK)

        self.session_keys = None
        self.dh_first_part = None
        self.dh_secret = None
        self.address = None
        self.public_key = public_key

    @property
    def host(self):
        """
        The hop's hostname
        """
        if self.address:
            return self.address[0]
        return " UNKNOWN HOST "

    @property
    def port(self):
        """
        The hop's port
        """
        if self.address:
            return self.address[1]
        return " UNKNOWN PORT "

    @property
    def node_id(self):
        """
        The hop's nodeid
        """
        if self.public_key:
            return self.public_key.key_to_hash()

        raise RuntimeError("nodeid unknown")

    @property
    def node_public_key(self):
        """
        The hop's public_key
        """
        if self.public_key:
            return self.public_key.key_to_bin()

        raise RuntimeError("public key unknown")


class RelayRoute(object):

    """
    Relay object containing the destination circuit, socket address and whether
    it is online or not
    """

    def __init__(self, circuit_id, sock_addr, rendezvous_relay=False, mid=0):
        """
        @type sock_addr: (str, int)
        @type circuit_id: int
        @return:
        """

        self.sock_addr = sock_addr
        self.circuit_id = circuit_id
        self.creation_time = time.time()
        self.last_incoming = time.time()
        self.bytes_up = self.bytes_down = 0
        self.rendezvous_relay = rendezvous_relay
        self.mid = 0

class RendezvousPoint(object):

    def __init__(self, circuit, cookie, finished_callback):
        self.circuit = circuit
        self.cookie = cookie
        self.finished_callback = finished_callback
        self.rp_info = None
