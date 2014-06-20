import time
import random
import logging

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.community.tunnel import crypto, CIRCUIT_STATE_READY, CIRCUIT_STATE_EXTENDING, ORIGINATOR, \
                                     PING_INTERVAL, ENDPOINT
from Tribler.community.tunnel.conversion import TunnelConversion
from Tribler.community.tunnel.exitsocket import ShortCircuitExitSocket, TunnelExitSocket
from Tribler.community.tunnel.payload import CreatePayload, CreatedPayload, ExtendPayload, ExtendedPayload, \
                                             PongPayload, PingPayload
from Tribler.community.tunnel.routing import Circuit, Hop, RelayRoute
from Tribler.community.tunnel.tests.test_libtorrent import LibtorrentTest
from Tribler.dispersy.authentication import NoAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DropMessage
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.logger import get_logger
from Tribler.dispersy.requestcache import NumberCache, RandomNumberCache

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)


def preprocess_messages(func):
    def wrap(self, messages):
        # Work on a copy, or dispersy will get upset.
        messages = messages[:]
        for i in range(len(messages) - 1, -1, -1):
            message = messages[i]
            circuit_id = message.payload.circuit_id
            logger.debug("TunnelCommunity: got %s (%d) from %s", message.name, message.payload.circuit_id, message.candidate.sock_addr)
            # TODO: crypto
            # TODO: if crypto fails for relay messages, call remove_relay
            # TODO: if crypto fails for other messages, call remove_circuit
            if self.relay_message(circuit_id, message.name, message):
                message = messages.pop(i)
            else:
                if circuit_id in self.circuits:
                    self.circuits[circuit_id].beat_heart()
                    self.circuits[circuit_id].bytes_down += len(message.packet)
        return func(self, messages)
    return wrap


class CircuitRequestCache(NumberCache):

    def __init__(self, community, circuit):
        super(CircuitRequestCache, self).__init__(community.request_cache, u"anon-circuit", circuit.circuit_id)
        self.community = community
        self.circuit = circuit

    def on_timeout(self):
        if self.circuit.state != CIRCUIT_STATE_READY:
            reason = 'timeout on CircuitRequestCache, state = %s, candidate = %s' % (self.circuit.state, self.circuit.first_hop)
            self.community.remove_circuit(self.number, reason)


class CreatedRequestCache(NumberCache):

    def __init__(self, community, circuit_id, candidate, candidates):
        super(CreatedRequestCache, self).__init__(community.request_cache, u"anon-created", circuit_id)
        self.circuit_id = circuit_id
        self.candidate = candidate
        self.candidates = candidates

    def on_timeout(self):
        pass


class PingRequestCache(RandomNumberCache):

    def __init__(self, community, circuit):
        super(PingRequestCache, self).__init__(community._request_cache, u"ping")
        self.circuit = circuit
        self.community = community

    @property
    def timeout_delay(self):
        return 3.5 * PING_INTERVAL

    def on_timeout(self):
        if self.circuit.last_incoming < time.time() - self.timeout_delay:
            logger.debug("ForwardCommunity: no response on ping, circuit %d timed out", self.circuit.circuit_id)
            self.community.remove_circuit(self.circuit.circuit_id, 'ping timeout')


class TunnelSettings:

    def __init__(self):
        self.circuit_length = 3
        self.crypto = crypto.DefaultCrypto()


class TunnelCommunity(Community):

    def initialize(self, raw_server, tribler_session=None, settings=None):
        super(TunnelCommunity, self).initialize()

        self.raw_server = raw_server
        self.data_prefix = "fffffffe".decode("HEX")
        self.observers = []
        self.circuits = {}
        self.directions = {}
        self.relay_from_to = {}
        self.waiting_for = set()
        self.exit_sockets = {}
        self.circuit_pools = []
        self.notifier = None
        self.settings = settings if settings else TunnelSettings()
        self.settings.crypto.set_proxy(self)

        self._dispersy.endpoint.listen_to(self.data_prefix, self.on_data)

        self._pending_tasks["do_circuits"] = lc = LoopingCall(self.do_circuits)
        lc.start(5, now=True)

        self._pending_tasks["do_ping"] = lc = LoopingCall(self.do_ping)
        lc.start(PING_INTERVAL)

        if tribler_session:
            from Tribler.Core.CacheDB.Notifier import Notifier
            self.notifier = Notifier.getInstance()
            reactor.callLater(0, lambda: LibtorrentTest(self, tribler_session, 60))

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Mon Jun 16 15:31:00 2014
        # curve: NID_sect571r1
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040380695ccdb2f64d6fc21f070cf151f3bd3e159609a642aaa023b3620d3
        # f452a4d6114a9031c1f1155fdc6c3d89689c02ec7205e306a1ea397d59a8e0056702d704d97d68a70a9b000e2b902d2ffb92107125d24d91cb771f11
        # cea88b157c8d6421eaecc1ddb9d6dad4a907373f08b3f1eb12438d290f282fe2a5cec9f2deb71b23a77e74a787caf9faf2a202adbf728
        # pub-sha1 f292e197efee5cd785c3f89d6e4826fd08c556f4
        #-----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQDgGlczbL2TW/CHwcM8VHzvT4Vlgmm
        # QqqgI7NiDT9FKk1hFKkDHB8RVf3Gw9iWicAuxyBeMGoeo5fVmo4AVnAtcE2X1opw
        # qbAA4rkC0v+5IQcSXSTZHLdx8RzqiLFXyNZCHq7MHdudba1KkHNz8Is/HrEkONKQ
        # 8oL+Klzsny3rcbI6d+dKeHyvn68qICrb9yg=
        #-----END PUBLIC KEY-----

        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040380695ccdb2f64d6fc21f070cf151f3bd3e159609a642aaa023b3620d3f452a4d6114a9031c1f1155fdc6c3d89689c02ec7205e306a1ea397d59a8e0056702d704d97d68a70a9b000e2b902d2ffb92107125d24d91cb771f11cea88b157c8d6421eaecc1ddb9d6dad4a907373f08b3f1eb12438d290f282fe2a5cec9f2deb71b23a77e74a787caf9faf2a202adbf728".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def initiate_meta_messages(self):
        return super(TunnelCommunity, self).initiate_meta_messages() + \
               [Message(self, u"create", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), CreatePayload(), self.check_create, self.on_create),
                Message(self, u"created", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), CreatedPayload(), self.check_created, self.on_created),
                Message(self, u"extend", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), ExtendPayload(), self.check_extend, self.on_extend),
                Message(self, u"extended", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), ExtendedPayload(), self.check_extended, self.on_extended),
                Message(self, u"ping", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PingPayload(), self._generic_timeline_check, self.on_ping),
                Message(self, u"pong", NoAuthentication(), PublicResolution(), DirectDistribution(), CandidateDestination(), PongPayload(), self.check_pong, self.on_pong)]

    def initiate_conversions(self):
        return [DefaultConversion(self), TunnelConversion(self)]

    @property
    def crypto(self):
        return self.dispersy.crypto

    @property
    def packet_crypto(self):
        return self.settings.crypto

    def _generate_circuit_id(self, neighbour=None):
        circuit_id = random.getrandbits(32)

        # Prevent collisions.
        while circuit_id in self.circuits or (neighbour and (neighbour, circuit_id) in self.relay_from_to):
            circuit_id = random.getrandbits(32)

        return circuit_id

    def do_circuits(self):
        logger.error("TunnelCommunity: the %d pools want %d circuits", len(self.circuit_pools), sum(pool.lacking for pool in self.circuit_pools))

        circuits_needed = lambda: sum(pool.lacking for pool in self.circuit_pools)

        for _ in range(0, circuits_needed()):
            logger.debug("Need %d new circuits!", circuits_needed())
            goal_hops = self.settings.circuit_length

            if goal_hops == 0:
                circuit_id = self._generate_circuit_id()
                self.circuits[circuit_id] = Circuit(circuit_id, proxy=self)

                first_pool = next((pool for pool in self.circuit_pools if pool.lacking), None)
                if first_pool:
                    first_pool.fill(self.circuits[circuit_id])

            else:
                candidate = None
                hops = set([c.first_hop for c in self.circuits.values()])
                for c in self.dispersy_yield_verified_candidates():
                    if (c.sock_addr not in hops) and self.packet_crypto.is_key_compatible(c.get_member()._ec):
                        candidate = c
                        break

                if candidate != None:
                    try:
                        self.create_circuit(candidate, goal_hops)
                    except:
                        logger.exception("Error creating circuit while running __discover")

    def create_circuit(self, first_hop, goal_hops):
        if not (goal_hops > 0):
            raise ValueError("We can only create circuits with more than 0 hops using create_circuit()!")

        circuit_id = self._generate_circuit_id(first_hop.sock_addr)
        circuit = Circuit(circuit_id=circuit_id, goal_hops=goal_hops, first_hop=first_hop.sock_addr, proxy=self)

        self._request_cache.add(CircuitRequestCache(self, circuit))

        circuit.unverified_hop = Hop(first_hop.get_member()._ec)
        circuit.unverified_hop.address = first_hop.sock_addr

        logger.warning("TunnelCommunity: creating circuit %d of %d hops. Fist hop: %s:%d", circuit_id,
                       circuit.goal_hops, first_hop.sock_addr[0], first_hop.sock_addr[1])

        self.circuits[circuit_id] = circuit
        self.waiting_for.add(circuit_id)

        destination_key = first_hop.get_member()._ec
        circuit.bytes_up += self.send_message([Candidate(first_hop.sock_addr, False)], u"create", \
                                              (circuit_id, "", self.my_member.public_key, destination_key))
        return circuit

    def remove_circuit(self, circuit_id, additional_info=''):
        assert isinstance(circuit_id, (long, int)), type(circuit_id)

        if circuit_id in self.circuits:
            logger.error("TunnelCommunity: breaking circuit %d " + additional_info, circuit_id)

            circuit = self.circuits.pop(circuit_id)
            circuit.destroy()

            for observer in self.observers:
                observer.on_break_circuit(circuit)

            return True
        return False

    def remove_relay(self, relay_key, additional_info=''):
        if relay_key in self.relay_from_to:
            logger.error(("TunnelCommunity: breaking relay %d " + additional_info) % relay_key)

            # Only remove one side of the relay, this isn't as pretty but both sides have separate incoming timer,
            # hence after removing one side the other will follow.
            del self.relay_from_to[relay_key]

            for observer in self.observers:
                observer.on_break_relay(relay_key)

            return True
        return False

    @property
    def active_circuits(self):
        return {cid: c for cid, c in self.circuits.iteritems() if c.state == CIRCUIT_STATE_READY}

    def send_message(self, candidates, message_type, payload):
        meta = self.get_meta_message(message_type)
        message = meta.impl(distribution=(self.global_time,), payload=payload)
        return self.send_packet(candidates, message_type, message.packet)

    def send_packet(self, candidates, message_type, packet):
        # TODO: add crypto
        self.dispersy._endpoint.send(candidates, [packet], prefix=self.data_prefix if message_type == u"data" else None)
        self.statistics.increase_msg_count(u"outgoing", message_type, len(candidates))
        logger.debug("TunnelCommunity: send %s to %s candidates: %s", message_type, len(candidates), map(str, candidates))
        return len(packet)

    def relay_message(self, circuit_id, message_type, message):
        return self.relay_packet(circuit_id, message_type, message.packet)

    def relay_packet(self, circuit_id, message_type, packet):
        if circuit_id > 0 and circuit_id in self.relay_from_to and not circuit_id in self.waiting_for:
            next_relay = self.relay_from_to[circuit_id]

            if next_relay.circuit_id in self.relay_from_to:
                this_relay = self.relay_from_to[next_relay.circuit_id]
                this_relay.last_incoming = time.time()

            packet = TunnelConversion.swap_circuit_id(packet, message_type, circuit_id, next_relay.circuit_id)
            self.send_packet([Candidate(next_relay.sock_addr, False)], message_type, packet)
            return True
        return False

    def check_create(self, messages):
        for message in messages:
            yield message

    def check_created(self, messages):
        for message in messages:
            yield message

    def check_extend(self, messages):
        for message in messages:
            yield message

    def check_extended(self, messages):
        for message in messages:
            yield message

    def check_pong(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            relay = circuit_id > 0 and circuit_id in self.relay_from_to and not circuit_id in self.waiting_for
            if not relay:
                request = self._request_cache.get(u"ping", message.payload.identifier)
                if not request:
                    yield DropMessage(message, "invalid response identifier")
                    continue

            yield message

    def _ours_on_created_extended(self, circuit, message):
        self.request_cache.pop(u"anon-circuit", circuit.circuit_id)

        candidate_list = message.payload.candidate_list
        circuit.add_hop(circuit.unverified_hop)
        circuit.unverified_hop = None

        for ignore_candidate in [self.my_member.public_key] + [hop.public_key for hop in circuit.hops]:
            if ignore_candidate in candidate_list:
                candidate_list.remove(ignore_candidate)

        for i in range(len(candidate_list) - 1, -1, -1):
            public_key = self.crypto.key_from_public_bin(candidate_list[i])
            if not self.packet_crypto.is_key_compatible(public_key):
                candidate_list.pop(i)

        if circuit.state == CIRCUIT_STATE_EXTENDING:
            extend_hop_public_bin = next(iter(candidate_list), None)
            if extend_hop_public_bin:
                extend_hop_public_key = self.dispersy.crypto.key_from_public_bin(extend_hop_public_bin)
                hashed_public_key = self.dispersy.crypto.key_to_hash(extend_hop_public_key)
                circuit.unverified_hop = Hop(extend_hop_public_key)

                logger.info("TunnelCommunity: extending circuit %d with %s", circuit.circuit_id, hashed_public_key)
                circuit.bytes_up += self.send_message([Candidate(circuit.first_hop, False)], u"extend", \
                                                      (circuit.circuit_id, '', extend_hop_public_bin))
            else:
                self.remove_circuit(circuit.circuit_id, "no candidates (with key) to extend, bailing out.")

        elif circuit.state == CIRCUIT_STATE_READY:
            first_pool = next((pool for pool in self.circuit_pools if pool.lacking), None)
            if first_pool:
                first_pool.fill(circuit)
        else:
            return

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_CREATED, NTFY_EXTENDED
            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_CREATED if len(circuit.hops) == 1 else NTFY_EXTENDED, circuit)

    @preprocess_messages
    def on_create(self, messages):
        for message in messages:
            candidate = message.candidate
            circuit_id = message.payload.circuit_id
            self.directions[circuit_id] = ENDPOINT
            logger.info('TunnelCommunity: we joined circuit %d with neighbour %s', circuit_id, candidate.sock_addr)

            candidates = {}
            for c in self.dispersy_yield_verified_candidates():
                if self.packet_crypto.is_candidate_compatible(c):
                    candidates[c.get_member().public_key] = c
                    if len(candidates) >= 4:
                        break

            self._request_cache.add(CreatedRequestCache(self, circuit_id, candidate, candidates))

            if self.notifier:
                from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_JOINED
                self.notifier.notify(NTFY_ANONTUNNEL, NTFY_JOINED, candidate.sock_addr, circuit_id)

            self.send_message([candidate], u"created", (circuit_id, '', candidates.keys(), message))

    @preprocess_messages
    def on_created(self, messages):
        for message in messages:
            candidate = message.candidate
            circuit_id = message.payload.circuit_id

            if circuit_id not in self.waiting_for:
                logger.error("TunnelCommunity: got an unexpected CREATED message for circuit %d from %s:%d", circuit_id, *candidate.sock_addr)
                continue
            self.waiting_for.remove(circuit_id)

            self.directions[circuit_id] = ORIGINATOR
            if circuit_id in self.relay_from_to:
                logger.debug("TunnelCommunity: got CREATED message forward as EXTENDED to origin.")

                forwarding_relay = self.relay_from_to[circuit_id]
                self.send_message([Candidate(forwarding_relay.sock_addr, False)], u"extended", \
                                  (forwarding_relay.circuit_id, message.payload.key, message.payload.candidate_list))

            # Circuit is ours.
            if circuit_id in self.circuits:
                circuit = self.circuits[circuit_id]
                self._ours_on_created_extended(circuit, message)

    @preprocess_messages
    def on_extend(self, messages):
        for message in messages:
            if message.payload.extend_with:
                candidate = message.candidate
                circuit_id = message.payload.circuit_id
                cache = self.request_cache.pop(u"anon-created", circuit_id)

                if not cache:
                    logger.warning("TunnelCommunity: cannot find created cache for circuit %d", circuit_id)
                    continue

                extend_candidate = cache.candidates[message.payload.extend_with]
                logger.warning("TunnelCommunity: on_extend send CREATE for circuit (%s, %d) to %s:%d!", candidate.sock_addr,
                                circuit_id, extend_candidate.sock_addr[0], extend_candidate.sock_addr[1])
            else:
                logger.error("TunnelCommunity: cancelling EXTEND, no candidate!")
                continue

            if circuit_id in self.relay_from_to:
                current_relay = self.relay_from_to.pop(circuit_id)
                assert not current_relay.online, "shouldn't be called whenever relay is online the extend message should have been forwarded"

                # We will just forget the attempt and try again, possible with another candidate.
                del self.relay_from_to[current_relay.circuit_id]

            new_circuit_id = self._generate_circuit_id(extend_candidate.sock_addr)

            self.waiting_for.add(new_circuit_id)
            self.relay_from_to[new_circuit_id] = RelayRoute(circuit_id, candidate.sock_addr)
            self.relay_from_to[circuit_id] = RelayRoute(new_circuit_id, extend_candidate.sock_addr)

            self.directions[new_circuit_id] = ORIGINATOR
            self.directions[circuit_id] = ENDPOINT

            logger.info("TunnelCommunity: extending circuit, got candidate with IP %s:%d from cache", *extend_candidate.sock_addr)

            destination_key = extend_candidate.get_member()._ec
            self.send_message([extend_candidate], u"create", (new_circuit_id, message.payload.key, self.my_member.public_key, destination_key))

    @preprocess_messages
    def on_extended(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            circuit = self.circuits[circuit_id]
            self._ours_on_created_extended(circuit, message)

    def on_data(self, sock_addr, packet):
        # If its our circuit, the messenger is the candidate assigned to that circuit and the DATA's destination
        # is set to the zero-address then the packet is from the outside world and addressed to us from.

        circuit_id, destination, origin, data = TunnelConversion.decode_data(packet)

        logger.debug("TunnelCommunity: got data (%d) from %s", circuit_id, sock_addr)

        if not self.relay_packet(circuit_id, u'data', packet):
            if circuit_id in self.circuits and origin and sock_addr == self.circuits[circuit_id].first_hop:
                self.circuits[circuit_id].beat_heart()
                self.circuits[circuit_id].bytes_down += len(packet)
                for observer in self.observers:
                    observer.on_incoming_from_tunnel(self, self.circuits[circuit_id], origin, data)

            # It is not our circuit so we got it from a relay, we need to EXIT it!
            else:
                logger.debug("TunnelCommunity: data for circuit %d exiting tunnel (%s)", circuit_id, destination)
                if destination != ('0.0.0.0', 0):
                    self.exit_data(circuit_id, sock_addr, destination, data)

    @preprocess_messages
    def on_ping(self, messages):
        for message in messages:
            self.send_message([message.candidate], u"pong", (message.payload.circuit_id, message.payload.identifier))
            logger.debug("TunnelCommunity: got ping from %s", message.candidate)

    @preprocess_messages
    def on_pong(self, messages):
        for message in messages:
            self._request_cache.pop(u"ping", message.payload.identifier)
            logger.debug("TunnelCommunity: got pong from %s", message.candidate)

    def do_ping(self):
        # Remove inactive relays.
        dead_relays = [self.remove_relay(key, 'no activity') for key, relay in self.relay_from_to.items() \
                       if relay.last_incoming < time.time() - 60.0]
        logger.info("TunnelCommunity: removed %d relays", len(dead_relays))
        assert all(dead_relays)

        # Ping circuits. Pings are only sent to the first hop, subsequent hops will relay the ping.
        for circuit in self.active_circuits.values():
            if circuit.goal_hops > 0:
                cache = self._request_cache.add(PingRequestCache(self, circuit))
                circuit.bytes_up += self.send_message([Candidate(circuit.first_hop, False)], u"ping", (circuit.circuit_id, cache.number))

    def tunnel_data_to_end(self, ultimate_destination, data, circuit):
        if circuit.goal_hops == 0:
            self.exit_data(circuit, None, ultimate_destination, data)
        else:
            packet = TunnelConversion.encode_data(circuit.circuit_id, ultimate_destination, ('0.0.0.0', 0), data)
            circuit.bytes_up += self.send_packet([Candidate(circuit.first_hop, False)], u'data', packet)

    def tunnel_data_to_origin(self, circuit_id, sock_addr, source_address, data):
        packet = TunnelConversion.encode_data(circuit_id, ('0.0.0.0', 0), source_address, data)
        self.send_packet([Candidate(sock_addr, False)], u'data', packet)

    def exit_data(self, circuit_id, sock_addr, destination, data):
        if not (circuit_id in self.exit_sockets):
            if sock_addr == None:
                self.exit_sockets[circuit_id] = ShortCircuitExitSocket(self.raw_server, self, circuit_id, None)
            else:
                self.exit_sockets[circuit_id] = TunnelExitSocket(self.raw_server, self, circuit_id, sock_addr)
        try:
            self.exit_sockets[circuit_id].sendto(data, destination)
        except:
            logger.error("TunnelCommunity: dropping packets while EXITing data")
