import logging
import time
from twisted.internet import defer
from twisted.python.failure import Failure
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_READY, \
    CIRCUIT_STATE_BROKEN, CIRCUIT_STATE_EXTENDING
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, Candidate

__author__ = 'chris'


class Circuit:
    """ Circuit data structure storing the id, state and hops """

    def __init__(self, circuit_id, goal_hops=0, candidate=None, proxy=None,
                 deferred=None):
        """
        Instantiate a new Circuit data structure
        :type proxy: ProxyCommunity
        :param circuit_id: the id of the candidate circuit
        :param candidate: the first hop of the circuit
        :return: Circuit
        """

        self._broken = False
        self._hops = []
        self._logger = logging.getLogger(__name__)

        def __create_deferred():
            def __errback(error):
                self._logger.error("Unhandled deferred error: %s", error)
                return error

            d = defer.Deferred()
            d.addErrback(__errback)
            return d

        self.circuit_id = circuit_id
        self.candidate = candidate
        self.goal_hops = goal_hops
        self.deferred = deferred if deferred else __create_deferred()
        self.extend_strategy = None
        self.last_incoming = time.time()

        if proxy:
            self.__stats = proxy.global_stats.circuit_stats[circuit_id]
        else:
            self.__stats = None

        self.unverified_hop = None
        ''' :type : Hop '''


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

        if self.deferred and self.state == CIRCUIT_STATE_READY:
            self.deferred.callback(self)

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

    @property
    def ping_time_remaining(self):
        """
        The time left before we consider the circuit inactive, when it returns
        0 a PING must be sent to keep the circuit, including relays at its hop,
        alive.
        """
        too_old = time.time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incoming - too_old
        return diff if diff > 0 else 0

    def __contains__(self, other):
        if isinstance(other, Candidate):
            # TODO: should compare to a list here
            return other == self.candidate

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

        return self.proxy.tunnel_data_to_end(destination, payload, self)

    def destroy(self, reason='unknown'):
        """
        Destroys the circuit and calls the error callback of the circuit's
        deferred if it has not been called before

        @param str reason: the reason why the circuit is being destroyed
        """
        self._broken = True

        if self.deferred and not self.deferred.called:
            self.deferred.errback(
                Failure(Exception("Circuit broken, reason=%s" % reason)))


class Hop:
    """
    Circuit Hop containing the address, its public key and the first part of
    the Diffie-Hellman handshake
    """

    def __init__(self, address, pub_key, dh_first_part):
        """
        @param (str, int) address: the socket address of the hop
        @param M2Crypto.EC.EC_pub pub_key: the EC public key of the hop
        @param long dh_first_part: first part of the DH-handshake
        """
        self.address = address
        self.pub_key = pub_key
        self.session_key = None
        self.dh_first_part = dh_first_part

    @property
    def host(self):
        """
        The hop's hostname
        """
        return self.address[0]

    @property
    def port(self):
        """
        The hop's port
        """
        return self.address[1]


class RelayRoute(object):
    """
    Relay object containing the destination circuit, socket address and whether
    it is online or not
    """

    def __init__(self, circuit_id, sock_addr):
        """
        @type sock_addr: (str, int)
        @type circuit_id: int
        @return:
        """

        self.sock_addr = sock_addr
        self.circuit_id = circuit_id
        self.online = False
        self.last_incoming = time.time()

    @property
    def ping_time_remaining(self):
        """
        The time left before we consider the relay inactive
        """
        too_old = time.time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incoming - too_old
        return diff if diff > 0 else 0