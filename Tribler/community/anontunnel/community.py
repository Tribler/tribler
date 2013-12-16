import logging
import socket
from threading import RLock
from Tribler.community.anontunnel.ConnectionHandlers.CircuitReturnHandler import ShortCircuitReturnHandler, CircuitReturnHandler
from Tribler.dispersy.requestcache import NumberCache
logger = logging.getLogger(__name__)

from Tribler.community.anontunnel.globals import *
from Crypto.Random.random import randint
from Tribler.community.anontunnel import ExtendStrategies
from Tribler.community.anontunnel.CircuitLengthStrategies import ConstantCircuitLengthStrategy
from Tribler.community.anontunnel.SelectionStrategies import RandomSelectionStrategy
from traceback import print_exc

from time import time

from Tribler.community.anontunnel.conversion import ProxyConversion, \
    CustomProxyConversion

from Tribler.community.anontunnel.payload import StatsPayload, CreatedMessage, \
    PongMessage, CreateMessage, ExtendedWithMessage, PingMessage, DataMessage

from Tribler.dispersy.candidate import BootstrapCandidate, WalkCandidate, \
    Candidate
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution

class ProxySettings:
    def __init__(self):
        length = 1  # randint(1, 4)

        self.extend_strategy = ExtendStrategies.TrustThyNeighbour
        self.select_strategy = RandomSelectionStrategy(1)
        self.length_strategy = ConstantCircuitLengthStrategy(length)

class TunnelObserver():
    def on_state_change(self, community, state):
        pass

    def on_tunnel_data(self, community, origin, data):
        pass

    def on_tunnel_stats(self, community, candidate, stats):
        pass

class Circuit:
    """ Circuit data structure storing the id, status, first hop and all hops """

    def __init__(self, community, circuit_id, goal_hops=0, candidate=None):
        """
        Instantiate a new Circuit data structure

        :param circuit_id: the id of the candidate circuit
        :param candidate: the first hop of the circuit
        :return: Circuit
        """

        self.community = community
        self.circuit_id = circuit_id
        self.candidate = candidate
        self.hops = [candidate.sock_addr] if candidate else []
        self.goal_hops = goal_hops

        self.extend_strategy = None
        self.timestamp = None
        self.times = []
        self.bytes_up_list = []
        self.bytes_down_list = []

        self.bytes_down = [0, 0]
        self.bytes_up = [0, 0]

        self.speed_up = 0.0
        self.speed_down = 0.0
        self.last_incomming = time()

    @property
    def bytes_downloaded(self):
        return self.bytes_down[1]

    @property
    def bytes_uploaded(self):
        return self.bytes_up[1]

    @property
    def online(self):
        return self.goal_hops == len(self.hops)

    @property
    def state(self):
        if self.hops == None:
            return CIRCUIT_STATE_BROKEN

        if len(self.hops) < self.goal_hops:
            return CIRCUIT_STATE_EXTENDING
        else:
            return CIRCUIT_STATE_READY

    @property
    def ping_time_remaining(self):
        too_old = time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incomming - too_old
        return diff if diff > 0 else 0

    def __contains__(self, other):
        if isinstance(other, Candidate):
            # TODO: should compare to a list here
            return other == self.candidate


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

        self.last_incomming = time()

    @property
    def ping_time_remaining(self):
        too_old = time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incomming - too_old
        return diff if diff > 0 else 0

class ProxyCommunity(Community):

    @classmethod
    def get_master_members(cls, dispersy):
# generated: Wed Sep 18 22:47:22 2013
# curve: high <<< NID_sect571r1 >>>
# len: 571 bits ~ 144 bytes signature
# pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040460829f9bb72f0cb094904aa6f885ff70e1e98651e81119b1e7b42402f3c5cfa183d8d96738c40ffd909a70020488e3b59b67de57bb1ac5dec351d172fe692555898ac944b68c730590f850ab931c5732d5a9d573a7fe1f9dc8a9201bc3cb63ab182c9e485d08ff4ac294f09e16d3925930946f87e91ef9c40bbb4189f9c5af6696f57eec3b8f2f77e7ab56fd8d6d63
# pub-sha1 089515d307ed31a25eec2c54667ddcd2d402c041
#-----BEGIN PUBLIC KEY-----
# MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQEYIKfm7cvDLCUkEqm+IX/cOHphlHo
# ERmx57QkAvPFz6GD2NlnOMQP/ZCacAIEiOO1m2feV7saxd7DUdFy/mklVYmKyUS2
# jHMFkPhQq5McVzLVqdVzp/4fncipIBvDy2OrGCyeSF0I/0rClPCeFtOSWTCUb4fp
# HvnEC7tBifnFr2aW9X7sO48vd+erVv2NbWM=
#-----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040460829f9bb72f0cb094904aa6f885ff70e1e98651e81119b1e7b42402f3c5cfa183d8d96738c40ffd909a70020488e3b59b67de57bb1ac5dec351d172fe692555898ac944b68c730590f850ab931c5732d5a9d573a7fe1f9dc8a9201bc3cb63ab182c9e485d08ff4ac294f09e16d3925930946f87e91ef9c40bbb4189f9c5af6696f57eec3b8f2f77e7ab56fd8d6d63".decode("HEX")
        master = dispersy.get_member(master_key)
        return [master]

    @classmethod
    def load_community(cls, dispersy, master, my_member, raw_server, settings=None, integrate_with_tribler=True):
        try:
            dispersy.database.execute(u"SELECT 1 FROM community WHERE master = ?", (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(dispersy, master, my_member, my_member, raw_server, settings, integrate_with_tribler=integrate_with_tribler)
        else:
            return super(ProxyCommunity, cls).load_community(dispersy, master, raw_server, settings, integrate_with_tribler=integrate_with_tribler)

    @property
    def online(self):
        return self._online

    @online.setter
    def online(self, value):
        changed = value != self._online

        if changed:
            self._online = value
            for o in self.__observers:
                o.on_state_change(self, value)

    def __init__(self, dispersy, master_member, raw_server, settings=None, integrate_with_tribler=True):
        Community.__init__(self, dispersy, master_member)

        if not settings:
            settings = ProxySettings()

        self.lock = RLock()

        # Custom conversion
        self.prefix = 'f' * 22 + 'e'  # shouldn't this be "fffffffe".decode("HEX")?
        self.proxy_conversion = CustomProxyConversion(self.prefix)
        self.on_custom = {MESSAGE_CREATE: self.on_create,
                          MESSAGE_CREATED: self.on_created, MESSAGE_DATA: self.on_data, MESSAGE_EXTEND: self.on_extend,
                          MESSAGE_EXTENDED: self.on_extended, MESSAGE_PING: self.on_ping, MESSAGE_PONG: self.on_pong,
                          MESSAGE_PUNCTURE: self.on_puncture}
        self.__observers = []
        ''' :type : list of TunnelObserver'''

        # Replace endpoint
        dispersy.endpoint.bypass_prefix = self.prefix
        dispersy.endpoint.bypass_community = self

        self.circuits = {}
        self.relay_from_to = {}

        # Stats
        self.stats = {
            'bytes_enter': 0,
            'bytes_exit': 0,
            'bytes_returned': 0,
            'dropped_exit': 0,
            'packet_size': 0
        }

        self.circuit_length_strategy = settings.length_strategy
        self.circuit_selection_strategy = settings.select_strategy
        self.extend_strategy = settings.extend_strategy

        # Map destination address to the circuit to be used
        self.destination_circuit = {}
        self._exit_sockets = {}
        self.raw_server = raw_server

        self._online = False

        dispersy._callback.register(self.check_ready)
        dispersy._callback.register(self.ping_circuits)

        if integrate_with_tribler:
            from Tribler.Core.CacheDB.Notifier import Notifier
            self.notifier = Notifier.getInstance()
        else:
            self.notifier = None

    def add_observer(self, observer):
        assert isinstance(observer, TunnelObserver)
        self.__observers.append(observer)

        observer.on_state_change(self, self.online)

    def initiate_conversions(self):
        return [DefaultConversion(self), ProxyConversion(self)]

    def initiate_meta_messages(self):
        return [Message(
            self
            , u"stats"
            , MemberAuthentication()
            , PublicResolution()
            , LastSyncDistribution(synchronization_direction=u"DESC", priority=128, history_size=1)
            , CommunityDestination(node_count=10)
            , StatsPayload()
            , self._dispersy._generic_timeline_check
            , self.on_stats
        )]

    def _initialize_meta_messages(self):
        super(ProxyCommunity, self)._initialize_meta_messages()

        self._original_on_introduction_request = None
        self._original_on_introduction_response = None

        # replace the callbacks for the dispersy-introduction-request and
        # dispersy-introduction-response messages
        meta = self._meta_messages[u"dispersy-introduction-request"]
        self._original_on_introduction_request = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution,
                                                 meta.distribution, meta.destination, meta.payload, meta.check_callback,
                                                 self.on_introduction_request, meta.undo_callback, meta.batch)

        meta = self._meta_messages[u"dispersy-introduction-response"]
        self._original_on_introduction_response = meta.handle_callback
        self._meta_messages[meta.name] = Message(meta.community, meta.name, meta.authentication, meta.resolution,
                                                 meta.distribution, meta.destination, meta.payload, meta.check_callback,
                                                 self.on_introduction_response, meta.undo_callback, meta.batch)

        assert self._original_on_introduction_request
        assert self._original_on_introduction_response

    def on_introduction_request(self, messages):
        try:
            return self._original_on_introduction_request(messages)
        finally:
            for message in messages:
                self.on_member_heartbeat(message.candidate)

    def on_introduction_response(self, messages):
        try:
            return self._original_on_introduction_response(messages)
        finally:
            for message in messages:
                self.on_member_heartbeat(message.candidate)

    def on_stats(self, messages):
        for message in messages:
            for o in self.__observers:
                o.on_tunnel_stats(self, message.candidate, message.payload.stats)

    def send_stats(self, stats):
        meta = self.get_meta_message(u"stats")
        record = meta.impl(authentication=(self._my_member,),
                           distribution=(self.claim_global_time(),),
                           payload=(stats,))

        self.dispersy.store_update_forward([record], True, False, True)

    # END OF DISPERSY DEFINED MESSAGES
    # START OF CUSTOM MESSAGES

    def on_bypass_message(self, sock_addr, packet):
        dispersy = self._dispersy

        # TODO: we should attempt to get the candidate from the member_heartbeat dict
        # get_candidate has a garbage collector :P
        candidate = self.get_candidate(sock_addr) or Candidate(sock_addr, False)
        circuit_id, data = self.proxy_conversion.get_circuit_and_data(packet)
        relay_key = (candidate, circuit_id)
        packet_type = self.proxy_conversion.get_type(data)

        # TODO: remove this line
        if packet_type == chr(6):
            return

        logger.debug("GOT %s from %s:%d over circuit %d", MESSAGE_STRING_REPRESENTATION[packet_type], candidate.sock_addr[0], candidate.sock_addr[1], circuit_id)

        # First, relay packet if we know whom to forward message to for this circuit
        if circuit_id > 0 and relay_key in self.relay_from_to and self.relay_from_to[relay_key].online:
            next_relay = self.relay_from_to[relay_key]
            new_packet = self.prefix + self.proxy_conversion.add_circuit(data, next_relay.circuit_id)
            next_relay.bytes[1] += len(new_packet)

            this_relay_key = (next_relay.candidate, next_relay.circuit_id)
            if this_relay_key in self.relay_from_to:
                this_relay = self.relay_from_to[this_relay_key]
                this_relay.last_incomming = time()
                this_relay.bytes[0] += len(packet)

            self.send_packet(next_relay.candidate, circuit_id, packet_type, new_packet, relayed=True)
            self.dict_inc(dispersy.statistics.success, MESSAGE_STRING_REPRESENTATION[packet_type] + '-relayed')

        # We don't know where to relay this message to, must be for me?
        else:
            _, payload = self.proxy_conversion.decode(data)
            if circuit_id in self.circuits:
                self.circuits[circuit_id].last_incomming = time()

            if not self.on_custom[packet_type](circuit_id, candidate, payload):
                self.dict_inc(dispersy.statistics.success, MESSAGE_STRING_REPRESENTATION[packet_type] + '-ignored')
                logger.debug("Prev message was IGNORED")
            else:
                self.dict_inc(dispersy.statistics.success, MESSAGE_STRING_REPRESENTATION[packet_type])

    class CircuitRequestCache(NumberCache):

        @staticmethod
        def create_number(force_number= -1):
            return force_number if force_number >= 0 else IntroductionRequestCache.create_number()

        @staticmethod
        def create_identifier(number, force_number= -1):
            assert isinstance(number, (int, long)), type(number)
            return u"request-cache:circuit-request:%d" % (number,)

        def __init__(self, community, force_number):
            NumberCache.__init__(self, community._request_cache, force_number)
            self.community = community

        @property
        def timeout_delay(self):
            return 5.0

        @property
        def cleanup_delay(self):
            return 0.0

        def on_created(self):
            if self.circuit.state == CIRCUIT_STATE_EXTENDING:
                self.circuit.extend_strategy.extend()
            elif self.circuit.state == CIRCUIT_STATE_READY:
                self.on_success()

            if self.community.notifier:
                from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_CREATED
                self.community.notifier.notify(NTFY_ANONTUNNEL, NTFY_CREATED, self.circuit)

        def on_extended(self, extended_message):
            self.circuit.hops.append(extended_message.extended_with)

            if self.circuit.state == CIRCUIT_STATE_EXTENDING:
                self.circuit.extend_strategy.extend()

            elif self.circuit.state == CIRCUIT_STATE_READY:
                self.on_success()

            if self.community.notifier:
                from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_EXTENDED
                self.community.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, self.circuit)

        def on_success(self):
            if self.circuit.state == CIRCUIT_STATE_READY:
                logger.info("Circuit %d is ready", self.number)
                self.community._dispersy._callback.register(self.community._request_cache.pop, args=(self.identifier,))

        def on_timeout(self):
            if not self.circuit.state == CIRCUIT_STATE_READY:
                self.community.remove_circuit(self.number, 'timeout on CircuitRequestCache, state = %s' % self.circuit.state)

    def create_circuit(self, first_hop_candidate, extend_strategy=None):
        """ Create a new circuit, with one initial hop """

        circuit_id = self._generate_circuit_id(first_hop_candidate)
        cache = self._request_cache.add(ProxyCommunity.CircuitRequestCache(self, circuit_id))

        goal_hops = self.circuit_length_strategy.circuit_length()
        circuit = cache.circuit = Circuit(self, circuit_id, goal_hops, first_hop_candidate)
        circuit.extend_strategy = extend_strategy(self, circuit) if extend_strategy else self.extend_strategy(self, circuit)
        self.circuits[circuit_id] = circuit

        logger.info('Circuit %d is to be created, we want %d hops sending to %s:%d', circuit_id, circuit.goal_hops, first_hop_candidate.sock_addr[0], first_hop_candidate.sock_addr[1])
        self.send_message(first_hop_candidate, circuit_id, MESSAGE_CREATE, CreateMessage())
        return circuit

    def remove_circuit(self, circuit_id, additional_info=''):
        assert isinstance(circuit_id, (long, int)), type(circuit_id)

        if circuit_id in self.circuits:
            logger.info("Breaking circuit %d " + additional_info, circuit_id)

            # Delete from data structures
            if self.circuits[circuit_id].extend_strategy:
                self.circuits[circuit_id].extend_strategy.stop()
            del self.circuits[circuit_id]

            return True
        return False

    def remove_relay(self, relay_key):
        if relay_key in self.relay_from_to:
            logger.info("Breaking relay %s:%d %d" % (relay_key[0][0], relay_key[0][1], relay_key[1]))

            relay = self.relay_from_to[relay_key]

            # one side of the relay broke, removing both
            del self.relay_from_to[(relay.candidate, relay.circuit_id)]
            del self.relay_from_to[relay_key]

    def on_create(self, circuit_id, candidate, message):
        """ Handle incoming CREATE message, acknowledge the CREATE request with a CREATED reply """
        logger.info('We joined circuit %d with neighbour %s', circuit_id, candidate)

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_JOINED
            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_JOINED, candidate.sock_addr, circuit_id)

        return self.send_message(candidate, circuit_id, MESSAGE_CREATED, CreatedMessage())

    def on_created(self, circuit_id, candidate, message):
        """ Handle incoming CREATED messages relay them backwards towards the originator if necessary """
        request = self._dispersy._callback.call(self._request_cache.get, args=(ProxyCommunity.CircuitRequestCache.create_identifier(circuit_id),))
        if request:
            request.on_created()
            return True

        relay_key = (candidate, circuit_id)
        if relay_key in self.relay_from_to:
            created_to = candidate
            created_for = self.relay_from_to[(created_to, circuit_id)]

            # Mark link online such that no new extension attempts will be taken
            created_for.online = True
            self.relay_from_to[(created_for.candidate, created_for.circuit_id)].online = True

            self.send_message(created_for.candidate, created_for.circuit_id, MESSAGE_EXTENDED,
                              ExtendedWithMessage(created_to.sock_addr))

            logger.info('We have created a circuit requested by (%s:%d, %d) to (%s:%d, %d)',
                           created_for.candidate.sock_addr[0],
                           created_for.candidate.sock_addr[1],
                           created_for.circuit_id,
                           created_to.sock_addr[0],
                           created_to.sock_addr[1],
                           circuit_id
            )

            return True
        return False

    def on_data(self, circuit_id, candidate, message):
        """ Handles incoming DATA message, forwards it over the chain or over the internet if needed."""
        # TODO: what's happening here?, some magic averaging I guess
        self.stats['packet_size'] = 0.8 * self.stats['packet_size'] + 0.2 * len(message.data)

        if circuit_id in self.circuits \
            and message.destination == ("0.0.0.0", 0) \
            and candidate == self.circuits[circuit_id].candidate:

            self.circuits[circuit_id].last_incomming = time()
            self.circuits[circuit_id].bytes_down[1] += len(message.data)
            self.stats['bytes_returned'] += len(message.data)

            for observer in self.__observers:
                observer.on_tunnel_data(self, message.origin, message.data)

            return True

        # If it is not ours and we have nowhere to forward to then act as exit node
        if message.destination != ('0.0.0.0', 0):
            self.exit_data(circuit_id, candidate, message.destination, message.data)

            return True
        return False

    def on_extend(self, circuit_id, candidate, message):
        """ Upon reception of a EXTEND message the message
            is forwarded over the Circuit if possible. At the end of
            the circuit a CREATE request is send to the Proxy to
            extend the circuit with. It's CREATED reply will
            eventually be received and propagated back along the Circuit. """

        if message.extend_with:
            extend_with = self.get_candidate(message.extend_with) or Candidate(message.extend_with, False)
            logger.warning("We might be sending a CREATE to someone we don't know, sending to %s:%d!", message.host, message.port)
        else:
            extend_with = next(
                (x for x in self.dispersy_yield_verified_candidates()
                 if x and x != candidate),
                None
            )

        if not extend_with:
            return

        relay_key = (candidate, circuit_id)
        if relay_key in self.relay_from_to:
            current_relay = self.relay_from_to[relay_key]
            assert not current_relay.online, "shouldn't be called whenever relay is online, the extend message should have been forwarded"

            # We will just forget the attempt and try again, possible with another candidate
            old_to_key = current_relay.candidate, current_relay.circuit_id
            del self.relay_from_to[old_to_key]
            del self.relay_from_to[relay_key]

        new_circuit_id = self._generate_circuit_id(extend_with)
        to_key = (extend_with, new_circuit_id)

        self.relay_from_to[to_key] = RelayRoute(circuit_id, candidate)
        self.relay_from_to[relay_key] = RelayRoute(new_circuit_id, extend_with)

        return self.send_message(extend_with, new_circuit_id, MESSAGE_CREATE, CreateMessage())

    def on_extended(self, circuit_id, candidate, message):
        """ A circuit has been extended, forward the acknowledgment back
            to the origin of the EXTEND. If we are the origin update
            our records. """

        request = self._dispersy._callback.call(self._request_cache.get, args=(ProxyCommunity.CircuitRequestCache.create_identifier(circuit_id),))
        if request:
            request.on_extended(message)
            return True
        return False

    class PingRequestCache(NumberCache):

        @staticmethod
        def create_number(force_number= -1):
            return force_number if force_number >= 0 else IntroductionRequestCache.create_number()

        @staticmethod
        def create_identifier(number, force_number= -1):
            assert isinstance(number, (int, long)), type(number)
            return u"request-cache:ping-request:%d" % (number,)

        def __init__(self, community, force_number):
            NumberCache.__init__(self, community._request_cache, force_number)
            self.community = community

        @property
        def timeout_delay(self):
            return 5.0

        @property
        def cleanup_delay(self):
            return 0.0

        def on_pong(self):
            self.community._dispersy._callback.register(self.community._request_cache.pop, args=(self.identifier,))

        def on_timeout(self):
            self.community.remove_circuit(self.number, 'timeout on PingRequestCache')

    def create_ping(self, candidate, circuit_id):
        self._dispersy._callback.register(self._request_cache.add, args=(ProxyCommunity.PingRequestCache(self, circuit_id),))
        self.send_message(candidate, circuit_id, MESSAGE_PING, PingMessage())

    def on_ping(self, circuit_id, candidate, message):
        if circuit_id in self.circuits:
            return self.send_message(candidate, circuit_id, MESSAGE_PONG, PongMessage())
        return False

    def on_pong(self, circuit_id, candidate, message):
        request = self._dispersy._callback.call(self._request_cache.get, args=(ProxyCommunity.PingRequestCache.create_identifier(circuit_id),))
        if request:
            request.on_pong(message)
            return True
        return False

    def on_puncture(self, circuit_id, candidate, message):
        return

        introduce = Candidate(message.sock_addr, False)
        logger.debug("We are puncturing our NAT to %s:%d" % introduce.sock_addr)

        meta_puncture_request = self.get_meta_message(u"dispersy-puncture-request")
        puncture_message = meta_puncture_request.impl(distribution=(self.global_time,),
                                                      destination=(introduce,), payload=(
                                                      message.sock_addr, message.sock_addr, randint(0, 2 ** 16)))

        return self.dispersy.endpoint.send([introduce], [puncture_message.packet])


    # got introduction_request or introduction_response from candidate
    # not necessarily a new candidate
    def on_member_heartbeat(self, candidate):
        assert isinstance(candidate, WalkCandidate), type(candidate)
        if not isinstance(candidate, BootstrapCandidate):

            if len(self.circuits) < MAX_CIRCUITS_TO_CREATE and candidate not in self.circuits.values():
                self.create_circuit(candidate)

    def _generate_circuit_id(self, neighbour):
        # TODO: why is the circuit_id so small? The conversion is using a unsigned long.
        circuit_id = randint(1, 255)

        # prevent collisions
        while circuit_id in self.circuits or (neighbour, circuit_id) in self.relay_from_to:
            circuit_id = randint(1, 255)

        return circuit_id

    def send_message(self, destination, circuit_id, message_type, message):
        return self.send_packet(destination, circuit_id, message_type, self.proxy_conversion.encode(circuit_id, message_type, message))

    def send_packet(self, destination, circuit_id, message_type, packet, relayed=False):
        assert isinstance(destination, Candidate), type(destination)
        assert isinstance(packet, str), type(packet)
        assert packet.startswith(self.prefix)

        logger.debug("SEND %s to %s:%d over circuit %d", MESSAGE_STRING_REPRESENTATION[message_type], destination.sock_addr[0], destination.sock_addr[1], circuit_id)

        self.dict_inc(self.dispersy.statistics.outgoing, MESSAGE_STRING_REPRESENTATION[message_type] + ('-relayed' if relayed else ''), 1)

        # we need to make sure that this endpoint is threadsafe
        return self.dispersy.endpoint.send([destination], [packet])

    def dict_inc(self, statistics_dict, key, inc=1):
        self.dispersy._callback.register(self._dispersy.statistics.dict_inc, args=(statistics_dict, u"anontunnel-" + key, inc))

    # CIRCUIT STUFFS
    def get_circuits(self):
        return self.circuits.values()

    @property
    def active_circuits(self):
        # Circuit is active when it has received a CREATED for it and the final length and the length is 0
        return [circuit for circuit in self.circuits.values() if circuit.state == CIRCUIT_STATE_READY]

    def check_ready(self):
        while True:
            try:
                self.circuit_selection_strategy.try_select(self.active_circuits)
                self.online = True

            except BaseException:
                self.online = False

            finally:
                yield 1.0

    def ping_circuits(self):
        while True:
            try:
                to_be_removed = [self.remove_relay(relay_key, 'no activity') for relay_key, relay in self.relay_from_to.items() if relay.ping_time_remaining == 0]
                logger.info("removed %d relays", len(to_be_removed))
                assert all(to_be_removed)

                to_be_pinged = [circuit for circuit in self.circuits.values() if circuit.ping_time_remaining < PING_INTERVAL and circuit.candidate]
                logger.info("pinging %d circuits", len(to_be_pinged))
                for circuit in to_be_pinged:
                    self.create_ping(circuit.candidate, circuit.circuit_id)
            except:
                print_exc()

            yield PING_INTERVAL

    def exit_data(self, circuit_id, return_candidate, destination, data):
        logger.debug("EXIT DATA packet to %s", destination)

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

    def unlink_destinations(self, destinations):
        with self.lock:
            for destination in destinations:
                if destination in self.destination_circuit:
                    del self.destination_circuit[destination]

    def send_data(self, payload, circuit_id=None, address=None, ultimate_destination=None, origin=None):
        assert address is not None or ultimate_destination != ('0.0.0.0', None)
        assert address is not None or ultimate_destination is not None

        with self.lock:
            try:
                # If no circuit specified, pick one from the ACTIVE LIST
                if circuit_id is None and ultimate_destination is not None:
                    # Each destination may be tunneled over a SINGLE different circuit
                    circuit_id = self.destination_circuit.get(ultimate_destination, None)

                    if circuit_id is None or circuit_id not in [c.circuit_id for c in self.active_circuits]:
                        # Make sure the '0-hop circuit' is also a candidate for selection
                        circuit_id = self.circuit_selection_strategy.select(self.active_circuits).circuit_id
                        self.destination_circuit[ultimate_destination] = circuit_id
                        logger.info("SELECT circuit %d for %s:%d", circuit_id, *ultimate_destination)

                # If chosen the 0-hop circuit OR if there are no other circuits act as EXIT node ourselves
                if circuit_id == 0:
                    self.circuits[0].bytes_up[-1] += len(payload)
                    self.exit_data(0, None, ultimate_destination, payload)
                    return

                # If no address has been given, pick the first hop
                # Note: for packet forwarding address MUST be given
                if address is None:
                    if circuit_id in self.circuits and self.circuits[circuit_id].online:
                        address = self.circuits[circuit_id].candidate
                    else:
                        logger.warning("Dropping packets from unknown / broken circuit")
                        return

                self.send_message(address, circuit_id, MESSAGE_DATA,
                                  DataMessage(ultimate_destination, payload, origin))

                if origin is None:
                    self.circuits[circuit_id].bytes_up[1] += len(payload)

                logger.debug("Sending data with origin %s to %s over circuit %d with ultimate destination %s:%d",
                            origin, address, circuit_id, *ultimate_destination)
            except Exception, e:
                logger.exception(e)
