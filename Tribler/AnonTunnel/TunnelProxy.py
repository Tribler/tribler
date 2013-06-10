import logging
from Tribler.AnonTunnel.Socks5AnonTunnel import Socks5AnonTunnel

logger = logging.getLogger(__name__)


from CircuitReturnHandler import CircuitReturnHandler
from Observable import Observable

from collections import defaultdict, deque
from optparse import OptionParser
import random
import sys
import time
from Circuit import Circuit
from ProxyCommunity import ProxyCommunity
from ProxyConversion import DataPayload, ExtendPayload
from Relay import Relay
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import StandaloneEndpoint

from Socks5AnonTunnel import Socks5AnonTunnel

__author__ = 'Chris'

class TunnelProxy(Observable):
    @property
    def local_addresses(self):
        return {self.dispersy.lan_address, self.dispersy.wan_address}

    def __init__(self):
        """ Initialises the Proxy by starting Dispersy and joining
            the Proxy Overlay. """
        Observable.__init__(self)

        self.socket_server = None

        self._exit_sockets = {}

        self.done = False
        self.circuits = {}

        self.circuit_membership = defaultdict(set)

        # Routing tables
        self.relay_from_to = {}
        self.relay_to_from = {}

        # Queue of EXTEND request, circuit id is key of the dictionary
        self.extension_queue = defaultdict(deque)

        self.callback = Callback()
        self.endpoint = StandaloneEndpoint(10000)
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")
        self.dispersy.start()
        logger.info("Dispersy is listening on port %d" % self.dispersy.lan_address[1])

        # Create Community and bind events
        community = self.callback.call(self.join_proxy_overlay, (self.dispersy,))
        assert isinstance(community, ProxyCommunity)
        community.subscribe("on_create", self.on_create)
        community.subscribe("on_created", self.on_created)
        community.subscribe("on_extend", self.on_extend)
        community.subscribe("on_extended", self.on_extended)
        community.subscribe("on_data", self.on_data)
        community.subscribe("on_member_heartbeat", self.on_member_heartbeat)

        self.community = community

    def on_create(self, event):
        """ Handle incoming CREATE message, acknowledge the CREATE request with a CREATED reply """
        address = event.message.candidate.sock_addr
        msg = event.message.payload

        logger.info('We joined circuit %d with origin %s', msg.circuit_id, address)

        community = self.community
        assert isinstance(community, ProxyCommunity)

        community.send_created(address, msg.circuit_id)

    def on_created(self, event):
        """ Handle incoming CREATED messages relay them backwards towards the originator if necessary """

        address = event.message.candidate.sock_addr
        msg = event.message.payload

        if self.circuits.has_key(msg.circuit_id):
            circuit = self.circuits[msg.circuit_id]
            circuit.created = True
            logger.info('Circuit %d has been created', msg.circuit_id)
            self._perform_extension(circuit)
        else:
            created_for = self.relay_to_from[(address, msg.circuit_id)]
            extended_with = address

            community = self.community
            assert isinstance(community, ProxyCommunity)
            community.send_extended(created_for.from_address, msg.circuit_id, extended_with)

            logger.info('We have extended circuit %d for %s with %s', msg.circuit_id, created_for.from_address,
                        extended_with)

    def on_data(self, event):
        """ Handles incoming DATA message, forwards it over the chain or over the internet if needed."""

        address = event.message.candidate.sock_addr
        msg = event.message.payload
        assert isinstance(msg, DataPayload.Implementation)

        relay_key = (address, msg.circuit_id)
        community = self.community
        assert isinstance(community, ProxyCommunity)

        # If we can forward it along the chain, do so!
        if self.relay_from_to.has_key(relay_key):
            relay = self.relay_from_to[relay_key]

            community.send_data(relay.to_address, msg.circuit_id, msg.destination, msg.data)
            logger.info("Forwarding DATA packet from %s to %s", address, relay.to_address)

        # If message is meant for us, write it to output
        elif msg.destination in self.local_addresses or msg.destination == ("0.0.0.0",0):
            self.fire("on_data", data = msg)

        # If it is not ours and we have nowhere to forward to then act as exit node
        else:
            logger.info("EXIT DATA packet to %s", msg.destination)

            self.get_exit_socket(msg.circuit_id, address).sendto(msg.data, msg.destination)

    def get_exit_socket(self, circuit_id, address):
        if not (circuit_id in self._exit_sockets):
            assert isinstance(self.socket_server, Socks5AnonTunnel)
            self._exit_sockets[circuit_id] = self.socket_server.create_udp_socket()

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
        assert isinstance(community, ProxyCommunity)

        # If we can forward it along the chain, do so!
        if self.relay_from_to.has_key(relay_key):
            relay = self.relay_from_to[relay_key]

            community.send_extend(relay.to_address, msg.circuit_id
                , msg.extend_with)
            return
        else: # We are responsible for EXTENDING the circuit

            circuit_id = msg.circuit_id

            # Payload contains the address we want to invite to the circuit
            to_address = msg.extend_with

            relay = Relay(circuit_id, from_address, to_address)
            self.relay_from_to[(from_address, circuit_id)] = relay
            self.relay_to_from[(to_address, circuit_id)] = relay

            community.send_create(to_address, circuit_id)

    def on_extended(self, event):
        """ A circuit has been extended, forward the acknowledgment back
            to the origin of the EXTEND. If we are the origin update
            our records. """

        address = event.message.candidate.sock_addr
        msg = event.message.payload

        relay_key = (address, msg.circuit_id)
        community = self.community
        assert isinstance(community, ProxyCommunity)

        # If we can forward it along the chain, do so!
        if self.relay_to_from.has_key(relay_key):
            relay = self.relay_to_from[relay_key]
            community.send_extended(relay.from_address, msg.circuit_id
                , msg.extended_with)

        # If it is ours, update our records
        elif self.circuits.has_key(msg.circuit_id):
            circuit_id = msg.circuit_id
            extended_with = msg.extended_with

            self.circuits[circuit_id].hops.append(extended_with)
            self.circuit_membership[extended_with].add(circuit_id)
            logger.info('Circuit %d has been extended with node at address %s and contains now %d hops', circuit_id,
                        extended_with, len(self.circuits[circuit_id].hops))
            self._perform_extension(self.circuits[circuit_id])

    def create_circuit(self, first_hop, circuit_id=None):
        """ Create a new circuit, with one initial hop """

        address = first_hop.sock_addr

        if circuit_id is None:
            circuit_id = random.randint(0, 255)

        logger.info('Circuit %d is to be created', circuit_id)

        circuit = Circuit(circuit_id, address)
        self.circuits[circuit_id] = circuit
        self.circuit_membership[address].add(circuit_id)

        community = self.community
        assert isinstance(community, ProxyCommunity)
        community.send_create(address, circuit_id)

        return self.circuits[circuit_id]

    def _perform_extension(self, circuit):
        queue = self.extension_queue[circuit]

        if circuit.created and len(queue) > 0:
            address = queue.popleft()

            logger.info('Circuit %d is to be extended with node with address %s', circuit.id, address)

            community = self.community
            assert isinstance(community, ProxyCommunity)
            community.send_extend(circuit.address, circuit.id, address)

    def extend_circuit(self, circuit, address):
        self.extension_queue[circuit].append(address)

        if circuit.created:
            self._perform_extension(circuit)

    def join_proxy_overlay(self, dispersy):
        master_member = dispersy.get_temporary_member_from_id("-PROXY-OVERLAY-HASH-")
        my_member = dispersy.get_new_member()
        return ProxyCommunity.join_community(dispersy, master_member, my_member)

    def on_member_heartbeat(self, event):
        candidate = event.candidate
        if candidate.sock_addr not in self.circuit_membership:
            self.create_circuit(candidate)

        circuits = set(self.circuits).difference(self.circuit_membership[candidate.sock_addr])

        for circuit_id in circuits:
            self.extend_circuit(self.circuits[circuit_id], candidate.sock_addr)

    def send_stdin_to_destination(self, destination):
        while 1:
            try:
                buff = sys.stdin.readline()
            except KeyboardInterrupt:
                break

            if not buff:
                break

            while len(self.circuits) == 0:
                logger.info("Waiting for circuits to be made before sending data")
                time.sleep(1)

            circuit = self.circuits.values()[0]

            self.community.send_data(circuit.address, circuit.id, destination, buff)

    def stop(self):
        self.dispersy.stop()

    def send_data(self, payload, circuit_id = None, address = None,ultimate_destination = None, origin = None):
        if circuit_id is None:
            circuit_id = self.circuits.values()[0].id

        if address is None:
            address = self.circuits[circuit_id].address

        self.community.send_data(address, circuit_id, ultimate_destination, payload, origin)
        logger.info("Sending data with origin %s to %s over circuit %d with ultimate destination %s", origin, address, circuit_id, ultimate_destination)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-o', '--output',
                      default=None,
                      type=str,
                      help='An address in format host:port to send data to',
                      dest='destination')

    (options, args) = parser.parse_args()

    proxy = TunnelProxy()

    if options.destination is not None:
        host, port = options.destination.split(':')
        proxy.send_stdin_to_destination((host, int(port)))

    while 1:
        time.sleep(1)

    proxy.stop()