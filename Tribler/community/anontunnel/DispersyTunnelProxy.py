import logging
from Tribler.community.anontunnel.ConnectionHandlers.CircuitReturnHandler import CircuitReturnHandler, ShortCircuitReturnHandler
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_EXTENDED

MAX_CIRCUITS_TO_CREATE = 10

logger = logging.getLogger(__name__)

from Observable import Observable

from collections import defaultdict, deque
import random
# from ProxyCommunity import ProxyCommunity
from ProxyConversion import DataPayload, ExtendPayload

__author__ = 'Chris'


class Circuit(object):
    """ Circuit data structure storing the id, status, first hop and all hops """

    def __init__(self, circuit_id, address):
        """
        Instantiate a new Circuit data structure

        :param circuit_id: the id of the circuit
        :param address: the first hop of the circuit
        :return: Circuit
        """
        self.created = False
        self.id = circuit_id
        self.address = address
        self.hops = [address]


class RelayRoute(object):
    def __init__(self, circuit_id, address):
        self.address = address
        self.circuit_id = circuit_id


class DispersyTunnelProxy(Observable):
    def __init__(self, dispersy, community):
        """ Initialises the Proxy by starting Dispersy and joining
            the Proxy Overlay. """
        Observable.__init__(self)

        self.socket_server = None

        self._exit_sockets = {}

        self.done = False
        self.circuits = {}

        self.notifier = Notifier.getInstance()

        # Hashmap Candidate -> {circuits}
        self.circuit_membership = defaultdict(set)

        # Routing tables
        self.relay_from_to = {}

        # Queue of EXTEND request, circuit id is key of the dictionary
        self.extension_queue = defaultdict(int)
        self.local_addresses = {}
        self.community = None

        self.local_addresses = {dispersy.lan_address, dispersy.wan_address}

        community.subscribe("on_create", self.on_create)
        community.subscribe("on_created", self.on_created)
        community.subscribe("on_extend", self.on_extend)
        community.subscribe("on_extended", self.on_extended)
        community.subscribe("on_data", self.on_data)
        community.subscribe("on_break", self.on_break)
        community.subscribe("on_member_heartbeat", self.on_member_heartbeat)
        community.subscribe("on_member_exit", self.on_member_exit)

        self.community = community

    def on_break(self, event):
        address = event.message.candidate.sock_addr
        msg = event.message.payload
        assert isinstance(msg, DataPayload.Implementation)

        relay_key = (address, msg.circuit_id)
        community = self.community

        # If we can forward it along the chain, do so!
        if self.relay_from_to.has_key(relay_key):
            relay = self.relay_from_to[relay_key]

            community.send(u"data", relay.address, relay.circuit_id, msg.destination, msg.data)
            logger.info("Forwarding BREAK packet from %s to %s", address, relay.address)

            del self.relay_from_to[relay_key]
            logger.info("BREAK circuit %d", msg.circuit_id)

        # We build this circuit but now its dead
        elif msg.circuit_id in self.circuits:
            del self.circuits[msg.circuit_id]
            logger.info("BREAK circuit %d", msg.circuit_id)


    def on_create(self, event):
        """ Handle incoming CREATE message, acknowledge the CREATE request with a CREATED reply """
        address = event.message.candidate.sock_addr
        msg = event.message.payload

        logger.info('We joined circuit %d with origin %s', msg.circuit_id, address)

        community = self.community
        community.send(u"created", address, msg.circuit_id)

    def on_created(self, event):
        """ Handle incoming CREATED messages relay them backwards towards the originator if necessary """

        address = event.message.candidate.sock_addr
        msg = event.message.payload

        if self.circuits.has_key(msg.circuit_id):
            circuit = self.circuits[msg.circuit_id]
            circuit.created = True
            logger.info('Circuit %d has been created', msg.circuit_id)
            self._process_extension_queue()
        else:
            created_for = self.relay_from_to[(address, msg.circuit_id)]
            extended_with = address

            community = self.community
            community.send(u"extended", created_for.address, created_for.circuit_id, extended_with)

            logger.info('We have extended circuit (%s, %d) with (%s,%d)',
                        created_for.address,
                        created_for.circuit_id,
                        extended_with,
                        msg.circuit_id
            )

    def on_data(self, event):
        """ Handles incoming DATA message, forwards it over the chain or over the internet if needed."""

        direct_sender_address = event.message.candidate.sock_addr
        msg = event.message.payload
        assert isinstance(msg, DataPayload.Implementation)

        relay_key = (direct_sender_address, msg.circuit_id)
        community = self.community

        # If we can forward it along the chain, do so!
        if self.relay_from_to.has_key(relay_key):
            relay = self.relay_from_to[relay_key]

            community.send(u"data", relay.address, relay.circuit_id, msg.destination, msg.data, msg.origin)
            logger.info("Forwarding DATA packet from %s to %s", direct_sender_address, relay.address)

        # If message is meant for us, write it to output
        elif msg.destination in self.local_addresses or msg.destination == ("0.0.0.0", 0):
            self.fire("on_data", data=msg, sender=direct_sender_address)

        # If it is not ours and we have nowhere to forward to then act as exit node
        else:
            self.exit_data(msg.circuit_id, direct_sender_address, msg.destination, msg.data)

    def exit_data(self, circuit_id, direct_sender_address, destination, data):
        logger.info("EXIT DATA packet to %s", destination)
        self.get_exit_socket(circuit_id, direct_sender_address).sendto(data, destination)

    def get_exit_socket(self, circuit_id, address):

        if not (circuit_id in self._exit_sockets):
            # assert isinstance(self.socket_server, Socks5AnonTunnel.Soc)
            self._exit_sockets[circuit_id] = self.socket_server.create_udp_socket()

            if circuit_id is None:
                return_handler = ShortCircuitReturnHandler(self._exit_sockets[circuit_id], self, address)
            else:
                return_handler = CircuitReturnHandler(self._exit_sockets[circuit_id], self, circuit_id, address)

            self.socket_server.start_listening_udp(self._exit_sockets[circuit_id], return_handler)

        return self._exit_sockets[circuit_id]

    def on_extend(self, event):
        """ Upon reception of a EXTEND message the message
            is forwarded over the Circuit if possible. At the end of
            the circuit a CREATE request is send to the Proxy to
            extend the circuit with. It's CREATED reply will
            eventually be received and propagated back along the Circuit. """

        from_address = event.message.candidate.sock_addr
        msg = event.message.payload
        assert isinstance(msg, ExtendPayload.Implementation)

        relay_key = (from_address, msg.circuit_id)
        community = self.community

        # If we can forward it along the chain, do so!
        if self.relay_from_to.has_key(relay_key):
            relay = self.relay_from_to[relay_key]

            community.send(u"extend", relay.address, relay.circuit_id)
            return
        else:  # We are responsible for EXTENDING the circuit

            circuit_id = msg.circuit_id

            # Payload contains the address we want to invite to the circuit
            to_candidate = next(
                (x for x in self.community.dispersy_yield_random_candidates()
                 if x != event.message.candidate),
                None
            )

            if to_candidate:
                new_circuit_id = random.randint(1, 255)
                to_address = to_candidate.sock_addr

                self.relay_from_to[(to_address, new_circuit_id)] = RelayRoute(circuit_id, from_address)
                self.relay_from_to[(from_address, circuit_id)] = RelayRoute(new_circuit_id, to_address)

                community.send(u"create", to_address, new_circuit_id)

    def on_extended(self, event):
        """ A circuit has been extended, forward the acknowledgment back
            to the origin of the EXTEND. If we are the origin update
            our records. """

        address = event.message.candidate.sock_addr
        msg = event.message.payload

        relay_key = (address, msg.circuit_id)
        community = self.community

        # If we can forward it along the chain, do so!
        if self.relay_from_to.has_key(relay_key):
            relay = self.relay_from_to[relay_key]
            community.send(u"extended", relay.address, relay.circuit_id, msg.extended_with)
            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, relay.circuit_id, msg.extended_with, False)

        # If it is ours, update our records
        elif self.circuits.has_key(msg.circuit_id):
            circuit_id = msg.circuit_id
            extended_with = msg.extended_with

            self.circuits[circuit_id].hops.append(extended_with)
            self.circuit_membership[extended_with].add(circuit_id)
            logger.info('Circuit %d has been extended with node at address %s and contains now %d hops', circuit_id,
                        extended_with, len(self.circuits[circuit_id].hops))
            self._process_extension_queue()
            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, circuit_id, extended_with, True)

    def create_circuit(self, first_hop, circuit_id=None):
        """ Create a new circuit, with one initial hop """

        address = first_hop.sock_addr

        if circuit_id is None:
            circuit_id = random.randint(1, 255)

        logger.info('Circuit %d is to be created', circuit_id)

        circuit = Circuit(circuit_id, address)
        self.circuits[circuit_id] = circuit
        self.circuit_membership[address].add(circuit_id)

        community = self.community
        community.send(u"create", address, circuit_id)

        return self.circuits[circuit_id]

    def _process_extension_queue(self):
        for circuit in self.extension_queue.keys():
            queue = self.extension_queue[circuit]

            if circuit.created and queue > 0:
                self.extension_queue[circuit] -= 1
                logger.info('Circuit %d is to be extended', circuit.id)

                community = self.community
                community.send(u"extend", circuit.address, circuit.id)

    def extend_circuit(self, circuit):
        self.extension_queue[circuit] += 1

        if circuit.created:
            self._process_extension_queue()

    def on_member_heartbeat(self, event):
        candidate = event.candidate

        # At least store that we have seen this candidate
        self.circuit_membership[candidate] = {}

        # We dont want to create too many circuits
        if len(self.circuits) > MAX_CIRCUITS_TO_CREATE:
            return

        if candidate.sock_addr not in self.circuit_membership:
            self.create_circuit(candidate)

        self._process_extension_queue()

        # circuits = set(self.circuits).difference(self.circuit_membership[candidate.sock_addr])

        # for circuit_id in circuits:
        #    self.extend_circuit(self.circuits[circuit_id], candidate.sock_addr)

    def send_data(self, payload, circuit_id=None, address=None, ultimate_destination=None, origin=None):
        if circuit_id is None and len(self.circuits) == 0:
            self.exit_data(None, ultimate_destination, ultimate_destination, payload)
            return

        if circuit_id is None and len(self.circuits) > 0:
            circuit_id = self.circuits.values()[0].id

        if address is None:
            address = self.circuits[circuit_id].address

        self.community.send(u"data", address, circuit_id, ultimate_destination, payload, origin)
        logger.info("Sending data with origin %s to %s over circuit %d with ultimate destination %s", origin, address,
                    circuit_id, ultimate_destination)

    def break_circuit(self, circuit_id, address):
        # Give other members possibility to clean up

        logger.error("Breaking circuit %d due to %s:%d" % (circuit_id, address[0], address[1]))

        # TODO: investigate if this is a good idea, since it may help malicious nodes determine which nodes are part of the downstream part of the circuit.
        self.community.send(u"break", self.circuits[circuit_id].address, circuit_id)

        # Delete from data structures
        if circuit_id in self.circuits:
            del self.circuits[circuit_id]

        # Delete any memberships
        del self.circuit_membership[address]

        # Delete rules from routing tables
        relay_key = (address, circuit_id)
        if relay_key in self.relay_from_to:
            del self.relay_from_to[relay_key]


    def on_member_exit(self, event):
        candidate = event.member

        # We must invalidate all circuits that have this candidate in its hop list
        circuit_ids = list(self.circuit_membership[candidate.sock_addr])

        [self.break_circuit(circuit_id, candidate.sock_addr) for circuit_id in circuit_ids]
