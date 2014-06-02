import hashlib
import logging
import threading
import time
from M2Crypto.EC import EC_pub

from Tribler.community.anontunnel.events import TunnelObserver
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_READY, \
    CIRCUIT_STATE_BROKEN, CIRCUIT_STATE_EXTENDING, PING_INTERVAL
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, Candidate

__author__ = 'chris'


class Circuit:
    """ Circuit data structure storing the id, state and hops """

    def __init__(self, circuit_id, goal_hops=0, first_hop=None, proxy=None):
        """
        Instantiate a new Circuit data structure
        :type proxy: ProxyCommunity
        :param int circuit_id: the id of the candidate circuit
        :param (str, int) first_hop: the first hop of the circuit
        :return: Circuit
        """

        from Tribler.community.anontunnel.community import ProxyCommunity
        assert isinstance(circuit_id, long)
        assert isinstance(goal_hops, int)
        assert proxy is None or isinstance(proxy, ProxyCommunity)
        assert first_hop is None or isinstance(first_hop, tuple) and isinstance(first_hop[0], basestring) and isinstance(first_hop[0], int)

        self._broken = False
        self._hops = []
        self._logger = logging.getLogger(__name__)

        self.circuit_id = circuit_id
        self.first_hop = first_hop
        self.goal_hops = goal_hops
        self.extend_strategy = None
        self.last_incoming = time.time()

        self.proxy = proxy

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

        return self.proxy.tunnel_data_to_end(destination, payload, self)

    def destroy(self, reason='unknown'):
        """
        Destroys the circuit and calls the error callback of the circuit's
        deferred if it has not been called before

        @param str reason: the reason why the circuit is being destroyed
        """
        self._broken = True


class Hop:
    """
    Circuit Hop containing the address, its public key and the first part of
    the Diffie-Hellman handshake
    """

    def __init__(self, public_key=None):
        """
        @param None|EC_pub public_key: public key object of the hop
        """

        assert public_key is None or isinstance(public_key, EC_pub)

        self.session_key = None
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


class CircuitPool(TunnelObserver):
    def __init__(self, size, name):
        super(CircuitPool, self).__init__()

        self._logger = logging.getLogger(__name__)
        self._logger.info("Creating a circuit pool of size %d with name '%s'", size, name)

        self.lock = threading.RLock()
        self.size = size
        self.circuits = set()
        self.allocated_circuits = set()
        self.name = name

        self.observers = []

    def on_break_circuit(self, circuit):
        if circuit in self.circuits:
            self.remove_circuit(circuit)

    @property
    def lacking(self):
        return max(0, self.size - len(self.circuits))

    @property
    def available_circuits(self):
        return [circuit
                for circuit in self.circuits
                if circuit not in self.allocated_circuits]

    def remove_circuit(self, circuit):
        self._logger.info("Removing circuit %d from pool '%s'", circuit.circuit_id, self.name)
        with self.lock:
            self.circuits.remove(circuit)

    def fill(self, circuit):
        self._logger.info("Adding circuit %d to pool '%s'", circuit.circuit_id, self.name)

        with self.lock:
            self.circuits.add(circuit)
            for observer in self.observers:
                observer.on_circuit_added(self, circuit)

    def deallocate(self, circuit):
        self._logger.info("Deallocate circuit %d from pool '%s'", circuit.circuit_id, self.name)

        with self.lock:
            self.allocated_circuits.remove(circuit)

    def allocate(self):
        with self.lock:
            try:
                circuit = next((c for c in self.circuits if c not in self.allocated_circuits))
                self.allocated_circuits.add(circuit)
                self._logger.info("Allocate circuit %d from pool %s", circuit.circuit_id, self.name)

                return circuit

            except StopIteration:
                if not self.lacking:
                    self._logger.warning("Growing size of pool %s from %d to %d", self.name, self.size, self.size*2)
                    self.size *= 2

                raise NotEnoughCircuitsException()


class NotEnoughCircuitsException(Exception):
    pass