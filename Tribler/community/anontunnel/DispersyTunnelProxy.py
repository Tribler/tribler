from Tribler.community.anontunnel.ProxyMessage import PunctureMessage

MAX_CIRCUITS_TO_CREATE = 10

CIRCUIT_STATE_READY = 'READY'
CIRCUIT_STATE_CREATING = 'CREATING'
CIRCUIT_STATE_EXTENDING = 'EXTENDING'
CIRCUIT_STATE_BROKEN = 'BROKEN'

import logging
logger = logging.getLogger(__name__)

import socket
import threading
import time
from traceback import print_exc
from Tribler.community.anontunnel import ProxyMessage, ExtendStrategies
from Tribler.community.anontunnel.CircuitLengthStrategies import ConstantCircuitLengthStrategy
from Tribler.community.anontunnel.ConnectionHandlers.CircuitReturnHandler import CircuitReturnHandler, ShortCircuitReturnHandler
from Tribler.community.anontunnel.SelectionStrategies import LengthSelectionStrategy
from Tribler.community.anontunnel.TriblerNotifier import TriblerNotifier
from Tribler.dispersy.candidate import Candidate

__author__ = 'Chris'

logger = logging.getLogger(__name__)

import random
from Observable import Observable


class Circuit(Observable):
    """ Circuit data structure storing the id, status, first hop and all hops """
    @property
    def bytes_downloaded(self):
        return self.bytes_down[1]


    @property
    def bytes_uploaded(self):
        return self.bytes_up[1]

    @property
    def online(self):
        return self.created and self.goal_hops == len(self.hops)

    def __init__(self, circuit_id, candidate=None):
        Observable.__init__(self)

        """
        Instantiate a new Circuit data structure

        :param circuit_id: the id of the candidate circuit
        :param candidate: the first hop of the circuit
        :return: Circuit
        """

        self.created = False
        self.id = circuit_id
        self.candidate = candidate
        self.hops = [candidate.sock_addr] if candidate else []
        self.goal_hops = 0

        self.state = CIRCUIT_STATE_CREATING

        self.extend_strategy = None

        self.timestamp = None

        self.times = []
        self.bytes_up_list = []
        self.bytes_down_list = []

        self.bytes_down = [0, 0]
        self.bytes_up = [0, 0]

        self.speed_up = 0.0
        self.speed_down = 0.0

        self.last_incoming = time.time()


class RelayRoute(object):
    def __init__(self, circuit_id, candidate):
        self.candidate = candidate
        self.circuit_id = circuit_id

        self.timestamp = None

        self.times = []
        self.bytes_list = []
        self.bytes = [0, 0]
        self.speed = 0

        self.online = False

class DispersyTunnelProxy(Observable):
    @property
    def online(self):
        return self.__online

    @online.setter
    def online(self, value):
        if value == self.__online:
            return

        self.__online = value

        if value:
            self.fire("on_ready", trigger_on_subscribe=True)
        else:
            self.fire("on_down")

    @property
    def record_stats(self):
        return self._record_stats

    @record_stats.setter
    def record_stats(self, value):
        previous_value = self._record_stats
        self._record_stats = value

        # clear old stats before recording new ones
        if value and not previous_value:
            with self.lock:
                for circuit in self.active_circuits:
                    circuit.bytes_down_list = circuit.bytes_down_list[:-1]
                    circuit.bytes_up_list = circuit.bytes_up_list[:-1]

                    circuit.times = [circuit.timestamp]

                for relay in self.relay_from_to.values():
                    relay.bytes_list = relay.bytes_list[:-1]

                    relay.times = [relay.timestamp]

                logger.error("Recording stats from NOW")

    @property
    def active_circuits(self):
        # Circuit is active when it has received a CREATED for it and the final length and the length is 0
        return [circuit for circuit in self.get_circuits() if
                circuit.state == CIRCUIT_STATE_READY and circuit.goal_hops == len(circuit.hops)]

    def get_circuits(self):
        return self.circuits.values()

    def get_relays(self):
        return self.relay_from_to.values()

    def __init__(self, raw_server):
        """ Initialises the Proxy by starting Dispersy and joining
            the Proxy Overlay. """
        Observable.__init__(self)

        self.prefix = 'f'*22 + 'e'

        self.__online = False
        self.share_stats = False
        self.callback = None

        self.raw_server = raw_server
        self._record_stats = False

        self._exit_sockets = {}

        self.done = False
        self.circuits = {}

        self.member_heartbeat = {}

        # Add 0-hop circuit
        self.circuits[0] = Circuit(0)
        self.circuits[0].state = CIRCUIT_STATE_READY

        self.joined = set()

        self.lock = threading.RLock()

        # Map destination address to the circuit to be used
        self.destination_circuit = {}

        # Routing tables
        self.relay_from_to = {}
        self.circuit_tag = {}

        self.circuit_length_strategy = ConstantCircuitLengthStrategy(2)# RandomCircuitLengthStrategy(1,4)
        self.circuit_selection_strategy = LengthSelectionStrategy(2,2)# (min_population_size=4)

        self.extend_strategy = ExtendStrategies.RandomAPriori

        self.message_observer = Observable()

        self.community = None
        self.stats = {
            'bytes_enter': 0,
            'bytes_exit': 0,
            'bytes_returned': 0,
            'dropped_exit': 0,
            'packet_size': 0
        }

    def clear_state(self):
        self.destination_circuit.clear()

    def setup_keep_alive(self):
        def cleanup_dead_circuits():
            while True:
                logger.info("cleanup_dead_circuits")
                try:
                    with self.lock:
                        for circuit in self.circuits.values():
                            if circuit.candidate:
                                self.send_message(circuit.candidate, circuit.id, ProxyMessage.MESSAGE_PING, ProxyMessage.PingMessage())

                        for address, circuit_id in self.joined:
                            self.send_message(address, circuit_id, ProxyMessage.MESSAGE_PING, ProxyMessage.PingMessage())

                        for relay in self.relay_from_to.values():
                            self.send_message(relay.candidate, relay.circuit_id, ProxyMessage.MESSAGE_PING, ProxyMessage.PingMessage())

                        timeout = 10.0

                        dead_circuits = [c for c in self.circuits.values() if c.goal_hops > 0 and c.state is not CIRCUIT_STATE_BROKEN and c.last_incoming < time.time() - timeout]

                        for circuit in dead_circuits:
                            self.break_circuit(circuit.id)
                except:
                    print_exc()

                # rerun over 3 seconds
                yield 2.0

        self.callback.register(cleanup_dead_circuits, priority=0)

    def on_bypass_message(self, sock_addr, packet):
        candidate = self.community.candidates.get(sock_addr) or Candidate(sock_addr, False)

        buffer = packet[len(self.prefix):]

        circuit_id, data = ProxyMessage.get_circuit_and_data(buffer)

        if circuit_id > 0:
            with self.lock:
                if circuit_id in self.circuits:
                    self.circuits[circuit_id].last_incoming = time.time()

        relay_key = (candidate, circuit_id)

        if circuit_id > 0 and relay_key in self.relay_from_to and self.relay_from_to[relay_key].online:
            relay = self.relay_from_to[relay_key]
            new_packet = self.prefix + ProxyMessage.change_circuit(buffer, relay.circuit_id)

            relay.bytes[1] += len(new_packet)
            self.community.dispersy.endpoint.send([relay.candidate], [new_packet])

            if ProxyMessage.get_type(packet) == ProxyMessage.MESSAGE_BREAK:
                # Route is dead :(
                del self.relay_from_to[relay_key]

        else:
            type, payload = ProxyMessage.parse_payload(data)
            self.message_observer.fire(type, circuit_id=circuit_id, candidate=candidate, message=payload)

    def on_puncture(self, circuit_id, candidate, message):
        assert isinstance(message, PunctureMessage)
        meta_puncture_request = self.community.get_meta_message(u"dispersy-puncture-request")
        introduced = Candidate(message.sock_addr, False)
        puncture_message = meta_puncture_request.impl(distribution=(self.community.global_time,), destination=(introduced,), payload=(message.sock_addr, message.sock_addr, random.randint(0, 2**16)))

        self.community.dispersy.endpoint.send([introduced], [puncture_message.packet])
        logger.warning("We are puncturing our NAT to %s:%d" % message.sock_addr)
        self.fire("puncture", False, introduced.sock_addr)

    def start(self, callback, community):
        self.community = community
        self.callback = callback

        self.community.dispersy.endpoint.bypass_prefix = self.prefix
        self.community.dispersy.endpoint.bypass_community = self

        self.message_observer.subscribe(ProxyMessage.MESSAGE_CREATE, self.on_create)
        self.message_observer.subscribe(ProxyMessage.MESSAGE_CREATED, self.on_created)
        self.message_observer.subscribe(ProxyMessage.MESSAGE_EXTEND, self.on_extend)
        self.message_observer.subscribe(ProxyMessage.MESSAGE_EXTENDED, self.on_extended)
        self.message_observer.subscribe(ProxyMessage.MESSAGE_DATA, self.on_data)
        self.message_observer.subscribe(ProxyMessage.MESSAGE_BREAK, self.on_break)
        self.message_observer.subscribe(ProxyMessage.MESSAGE_PUNCTURE, self.on_puncture)

        community.subscribe("on_member_heartbeat", self.on_member_heartbeat)

        self.setup_keep_alive()

        def check_ready():
            while True:
                try:
                    self.circuit_selection_strategy.select(self.active_circuits)
                    self.online = True
                except BaseException:
                    self.online = False
                finally:
                    yield 1.0

        def calc_speeds():
            while True:
                t2 = time.time()
                for c in self.circuits.values():
                    if c.timestamp is None:
                        c.timestamp = time.time()
                    elif c.timestamp < t2:

                        if self.record_stats and (len(c.bytes_up_list) == 0 or c.bytes_up[-1] != c.bytes_up_list[-1] and c.bytes_down[-1] != c.bytes_down_list[-1]):
                            c.bytes_up_list.append(c.bytes_up[-1])
                            c.bytes_down_list.append(c.bytes_down[-1])
                            c.times.append(t2)

                        c.speed_up = 1.0*(c.bytes_up[1]-c.bytes_up[0]) / (t2 - c.timestamp)
                        c.speed_down = 1.0*(c.bytes_down[1]-c.bytes_down[0]) / (t2 - c.timestamp)

                        c.timestamp = t2
                        c.bytes_up = [c.bytes_up[1], c.bytes_up[1]]
                        c.bytes_down = [c.bytes_down[1], c.bytes_down[1]]

                for r in self.relay_from_to.values():
                    if r.timestamp is None:
                        r.timestamp = time.time()
                    elif r.timestamp < t2:

                        if self.record_stats and (len(r.bytes_list) == 0 or r.bytes[-1] != r.bytes_list[-1]):
                            r.bytes_list.append(r.bytes[-1])
                            r.times.append(t2)

                        r.speed = 1.0*(r.bytes[1] - r.bytes[0]) / (t2 - r.timestamp)
                        r.timestamp = t2
                        r.bytes = [r.bytes[1], r.bytes[1]]

                yield 1.0

        def share_stats():
            while True:
                if self.share_stats:
                    logger.error("Sharing STATS")
                    for candidate in self.community.dispersy_yield_verified_candidates():
                        self.send_message(candidate, 0, ProxyMessage.MESSAGE_STATS, self._create_stats())

                yield 10.0

        callback.register(calc_speeds, priority=-10)
        callback.register(share_stats, priority=-10)
        callback.register(check_ready)


    def on_break(self, circuit_id, candidate, message):
        address = candidate
        assert isinstance(message, ProxyMessage.BreakMessage)

        relay_key = (candidate, circuit_id)
        community = self.community

        # We build this circuit but now its dead
        if circuit_id in self.circuits:
            self.break_circuit(circuit_id)


    def on_create(self, circuit_id, candidate, message):
        """ Handle incoming CREATE message, acknowledge the CREATE request with a CREATED reply """
        address = candidate

        logger.warning('We joined circuit %d with neighbour %s', circuit_id, address)

        self.send_message(address, circuit_id, ProxyMessage.MESSAGE_CREATED, ProxyMessage.CreatedMessage())

        with self.lock:
            self.joined.add((address, circuit_id))

        self.fire("joined", False, address, circuit_id)

    def on_created(self, circuit_id, candidate, message):
        """ Handle incoming CREATED messages relay them backwards towards the originator if necessary """
        with self.lock:
            if circuit_id in self.circuits:
                circuit = self.circuits[circuit_id]
                circuit.last_incoming = time.time()
                circuit.created = True
                logger.warning('Circuit %d has been created', circuit_id)

                # Instantiate extend strategy
                circuit.extend_strategy = self.extend_strategy(self, circuit)

                self.fire("circuit_created", circuit=circuit)
                circuit.fire("created")

            elif not self.relay_from_to.has_key((candidate, circuit_id)):
                logger.warning("Cannot route CREATED packet, probably concurrency overwrote routing rules!")
            else:

                # Mark link online such that no new extension attempts will be taken
                created_for = self.relay_from_to[(candidate, circuit_id)]
                created_for.online = True
                self.relay_from_to[(created_for.candidate, created_for.circuit_id)].online = True

                extended_with = candidate

                self.send_message(created_for.candidate, created_for.circuit_id, ProxyMessage.MESSAGE_EXTENDED, ProxyMessage.ExtendedWithMessage(extended_with.sock_addr))

                logger.warning('We have extended circuit (%s, %d) with (%s,%d)',
                               created_for.candidate,
                               created_for.circuit_id,
                               extended_with,
                               circuit_id
                )

                self.fire("circuit_extended_for", extended_for=(created_for.candidate, created_for.circuit_id),
                          extended_with=(extended_with, circuit_id))

    def on_data(self, circuit_id, candidate, message):
        """ Handles incoming DATA message, forwards it over the chain or over the internet if needed."""

        direct_sender_address = candidate.sock_addr
        assert isinstance(message, ProxyMessage.DataMessage)

        self.stats['packet_size'] = 0.8*self.stats['packet_size'] + 0.2*len(message.data)

        relay_key = (candidate, circuit_id)
        if circuit_id in self.circuits \
            and message.destination == ("0.0.0.0", 0) \
            and candidate == self.circuits[circuit_id].candidate:

            self.circuits[circuit_id].last_incoming = time.time()
            self.circuits[circuit_id].bytes_down[1] += len(message.data)
            self.stats['bytes_returned'] += len(message.data)
            self.fire("on_data", data=message, sender=direct_sender_address)

        # If it is not ours and we have nowhere to forward to then act as exit node
        elif message.destination != ('0.0.0.0', 0):
            self.exit_data(circuit_id, candidate, message.destination, message.data)

    def exit_data(self, circuit_id, return_candidate, destination, data):
        if __debug__:
            logger.info("EXIT DATA packet to %s", destination)

        self.circuits[0].bytes_up[1] += len(data)
        self.stats['bytes_exit'] += len(data)

        try:
            self.get_exit_socket(circuit_id, return_candidate).sendto(data, destination)
        except socket.error:
            self.stats['dropped_exit'] += 1
            pass

    def get_exit_socket(self, circuit_id, address):

        # If we don't have an exit socket yet for this socket, create one

        if not (circuit_id in self._exit_sockets):
            self._exit_sockets[circuit_id] = self.raw_server.create_udpsocket(0, "0.0.0.0")

            # There is a special case where the circuit_id is None, then we act as EXIT node ourselves. In this case we
            # create a ShortCircuitHandler that bypasses dispersy by patching ENTER packets directly into the Proxy's
            # on_data event.
            if circuit_id is 0:
                return_handler = ShortCircuitReturnHandler(self._exit_sockets[circuit_id], self, address)
            else:
                # Otherwise incoming ENTER packets should propagate back over the Dispersy tunnel, we use the
                # CircuitReturnHandler. It will use the DispersyTunnelProxy.send_data method to forward the data packet
                return_handler = CircuitReturnHandler(self._exit_sockets[circuit_id], self, circuit_id, address)

            self.raw_server.start_listening_udp(self._exit_sockets[circuit_id], return_handler)

        return self._exit_sockets[circuit_id]

    def on_extend(self, circuit_id, candidate, message):
        """ Upon reception of a EXTEND message the message
            is forwarded over the Circuit if possible. At the end of
            the circuit a CREATE request is send to the Proxy to
            extend the circuit with. It's CREATED reply will
            eventually be received and propagated back along the Circuit. """

        assert isinstance(message, ProxyMessage.ExtendMessage)

        relay_key = (candidate, circuit_id)
        community = self.community
        extend_with = self.community.get_candidate(message.extend_with) or Candidate(message.extend_with, False) if message.extend_with else None

        if extend_with:
            logger.warning("We might be sending a CREATE to someone we don't know, sending to %s:%d!", message.host, message.port)

        self.extend_for(candidate, circuit_id, extend_with)

    def send_message(self, destination, circuit_id, type, message):
        self.community.dispersy.endpoint.send([destination],[self.prefix + ProxyMessage.serialize(circuit_id, type, message)])

    def extend_for(self, from_candidate, from_circuit_id, to_candidate=None):
        from_key = (from_candidate, from_circuit_id)

        if from_key in self.relay_from_to:
            current_relay = self.relay_from_to[from_key]
            # If we have a next hop and the link is online, don't perform extension yourself!
            if self.relay_from_to[from_key].online:
                return
            else:
                # If its not online we will just forget the attempt and try again, possible with another candidate
                old_to_key = current_relay.candidate, current_relay.circuit_id
                del self.relay_from_to[old_to_key]
                del self.relay_from_to[from_key]

        if not to_candidate:
            # Payload contains the address we want to invite to the circuit
            to_candidate = next(
                (x for x in self.community.dispersy_yield_verified_candidates()
                 if x and x != from_candidate),
                None
            )

        if to_candidate:
            to_candidate = to_candidate
            new_circuit_id = self._generate_circuit_id(to_candidate)

            with self.lock:
                to_key = (to_candidate, new_circuit_id)

                self.relay_from_to[to_key] = RelayRoute(from_circuit_id, from_candidate)
                self.relay_from_to[from_key] = RelayRoute(new_circuit_id, to_candidate)

                self.send_message(to_candidate, new_circuit_id, ProxyMessage.MESSAGE_CREATE, ProxyMessage.CreateMessage)

            self.fire("circuit_extend", extend_for=(from_candidate, from_circuit_id),
                      extend_with=(to_candidate, new_circuit_id))


    def on_extended(self, circuit_id, candidate, message):
        """ A circuit has been extended, forward the acknowledgment back
            to the origin of the EXTEND. If we are the origin update
            our records. """

        with self.lock:
            relay_key = (candidate, circuit_id)
            community = self.community

            if self.circuits.has_key(circuit_id):
                circuit_id = circuit_id
                extended_with = message.extended_with

                circuit = self.circuits[circuit_id]
                circuit.last_incoming = time.time()

                addresses_in_use = [self.community.dispersy.wan_address, self.community.dispersy.lan_address]
                addresses_in_use.extend([
                    x.sock_addr if isinstance(x, Candidate) else x
                    for x in circuit.hops
                ])


                # CYCLE DETECTED!
                # Quick fix: delete the circuit!
                if extended_with in addresses_in_use:
                    with self.lock:
                        del self.circuits[circuit_id]

                    logger.error("[%d] CYCLE DETECTED %s in %s ", circuit_id, extended_with, addresses_in_use)
                    return

                # Decrease the EXTEND queue of this circuit if there is any
                # if circuit in self.extension_queue and self.extension_queue[circuit] > 0:
                circuit.hops.append(extended_with)

                if circuit.goal_hops == len(circuit.hops):
                    circuit.state = CIRCUIT_STATE_READY

                logger.warning('Circuit %d has been extended with node at address %s and contains now %d hops', circuit_id,
                               extended_with, len(self.circuits[circuit_id].hops))

                self.fire("circuit_extended", circuit=circuit)
                circuit.fire('extended')

    def _generate_circuit_id(self, neighbour):
        circuit_id = random.randint(1, 255)

        # prevent collisions
        while (neighbour, circuit_id) in self.relay_from_to:
            circuit_id = random.randint(1, 255)

        return circuit_id

    def create_circuit(self, first_hop, circuit_id=None):
        """ Create a new circuit, with one initial hop """

        # Generate a random circuit id that hasn't been used yet by us
        while circuit_id is None or circuit_id in self.circuits:
            circuit_id = self._generate_circuit_id(first_hop)

        circuit = Circuit(circuit_id, first_hop)
        circuit.goal_hops = self.circuit_length_strategy.circuit_length()

        logger.warning('Circuit %d is to be created, we want %d hops', circuit.id, circuit.goal_hops)

        with self.lock:
            self.circuits[circuit_id] = circuit

        community = self.community
        self.send_message(first_hop, circuit_id, ProxyMessage.MESSAGE_CREATE, ProxyMessage.CreateMessage())

        return self.circuits[circuit_id]

    def _create_stats(self):
        stats = {
            'bytes_enter': self.stats['bytes_enter'],
            'bytes_exit': self.stats['bytes_exit'],
            'bytes_return': self.stats['bytes_returned'],
            'circuits': [
                {
                    'bytes_down_list': c.bytes_down_list[::5],
                    'bytes_up_list': c.bytes_up_list[::5],
                    'times': c.times[::5],
                    'hops': len(c.hops)
                }
                for c in self.get_circuits()
            ],
            'relays': [
                {
                    'bytes_list': r.bytes_list[::5],
                    'times': r.times[::5],
                }
                for r in self.get_relays()
            ]
        }

        return stats

    def on_member_heartbeat(self, candidate):
        with self.lock:
            self.member_heartbeat[candidate] = time.time()

            if len(self.circuits) < MAX_CIRCUITS_TO_CREATE and candidate not in [c.candidate for c in self.circuits.values()]:
                self.create_circuit(candidate)

    def send_data(self, payload, circuit_id=None, address=None, ultimate_destination=None, origin=None):
        assert address is not None or ultimate_destination != ('0.0.0.0', None)
        assert address is not None or ultimate_destination is not None

        with self.lock:
            try:
                # If no circuit specified, pick one from the ACTIVE LIST
                if circuit_id is None and ultimate_destination is not None:
                    # Each destination may be tunneled over a SINGLE different circuit
                    circuit_id = self.destination_circuit.get(ultimate_destination, None)

                    if circuit_id is None or circuit_id not in [c.id for c in self.active_circuits]:
                        # Make sure the '0-hop circuit' is also a candidate for selection
                        circuit_id = self.circuit_selection_strategy.select(self.active_circuits).id
                        self.destination_circuit[ultimate_destination] = circuit_id
                        logger.warning("SELECT %d for %s", circuit_id, ultimate_destination)
                        self.fire("circuit_select", destination=ultimate_destination, circuit_id=circuit_id)


                # If chosen the 0-hop circuit OR if there are no other circuits act as EXIT node ourselves
                if circuit_id == 0:
                    self.exit_data(0, None, ultimate_destination, payload)
                    return

                # If no address has been given, pick the first hop
                # Note: for packet forwarding address MUST be given
                if address is None:
                    if circuit_id in self.circuits and self.circuits[circuit_id].created:
                        address = self.circuits[circuit_id].candidate
                    else:
                        logger.warning("Dropping packets from unknown / broken circuit")
                        return

                self.send_message(address, circuit_id, ProxyMessage.MESSAGE_DATA, ProxyMessage.DataMessage(ultimate_destination, payload, origin))

                if origin is None:
                    self.circuits[circuit_id].bytes_up[1] += len(payload)

                if __debug__:
                    logger.info("Sending data with origin %s to %s over circuit %d with ultimate destination %s",
                                origin, address, circuit_id, ultimate_destination)
            except Exception, e:
                logger.exception(e)

    def break_circuit(self, circuit_id):
        with self.lock:
            # Give other members possibility to clean up
            logger.error("Breaking circuit %d", circuit_id)

            self.fire("circuit_broken", circuit_id=circuit_id)

            # Delete from data structures
            if circuit_id in self.circuits:
                if self.circuits[circuit_id].extend_strategy:
                    self.circuits[circuit_id].extend_strategy.stop()

                del self.circuits[circuit_id]

            tunnels_going_down = len(self.active_circuits) == 1 # Don't count the 0-hop tunnel
            # Delete any ultimate destinations mapped to this circuit
            for key, value in self.destination_circuit.items():
                if value == circuit_id:
                    del self.destination_circuit[key]
                    tunnels_going_down = True


    def on_candidate_exit(self, candidate):
        """
        When a candidate is leaving the community we must break any associated circuits.
        """
        try:
            assert isinstance(candidate, Candidate)

            # We must invalidate all routes in which the candidate takes part
            for c in self.circuits.values():
                if c.candidate == candidate:
                    self.break_circuit(c.id)

            for relay_key in self.relay_from_to.keys():
                relay = self.relay_from_to[relay_key]

                if relay_key[0] == candidate:
                    logger.error("Sending BREAK to (%s, %d)", relay.candidate, relay.circuit_id)
                    self.send_message(relay.candidate, relay.circuit_id, ProxyMessage.MESSAGE_BREAK, ProxyMessage.BreakMessage())
                    del self.relay_from_to[relay_key]

                elif relay.candidate == candidate:
                    logger.error("Sending BREAK to (%s, %d)", relay_key[0], relay_key[1])
                    self.send_message(relay_key[0], relay_key[1], ProxyMessage.MESSAGE_BREAK, ProxyMessage.BreakMessage())
                    del self.relay_from_to[relay_key]
        except BaseException, e:
            logger.exception(e)


