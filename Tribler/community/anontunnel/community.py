# Python imports
import hashlib
import sys
import threading
import random
import time
from collections import defaultdict

# Tribler and Dispersy imports
from Tribler.Core.Utilities import encoding
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.requestcache import NumberCache
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.candidate import Candidate, WalkCandidate, \
    BootstrapCandidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.member import Member

# AnonTunnel imports
from Tribler.community.anontunnel import crypto
from Tribler.community.anontunnel import extendstrategies
from Tribler.community.anontunnel import selectionstrategies
from Tribler.community.anontunnel import lengthstrategies
from globals import *
from Tribler.community.anontunnel.payload import StatsPayload, CreateMessage, \
    CreatedMessage, ExtendedMessage, \
    PongMessage, PingMessage, DataMessage
from Tribler.community.anontunnel.conversion import CustomProxyConversion, \
    ProxyConversion, int_to_packed, packed_to_int

__author__ = 'chris'

import logging
logger = logging.getLogger()


class ProxySettings:
    def __init__(self):
        length = random.randint(1, 3)

        self.max_circuits = 4
        self.extend_strategy = extendstrategies.NeighbourSubset
        self.select_strategy = selectionstrategies.RoundRobinSelectionStrategy(
            self.max_circuits)
        self.length_strategy = lengthstrategies.ConstantCircuitLengthStrategy(
            length)
        self.crypto = crypto.DefaultCrypto()


class RelayRoute(object):
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
        too_old = time.time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incoming - too_old
        return diff if diff > 0 else 0


class Circuit:
    """ Circuit data structure storing the id, state and hops """

    def __init__(self, circuit_id, goal_hops=0, candidate=None, proxy=None):
        """
        Instantiate a new Circuit data structure
        :type proxy: ProxyCommunity
        :param circuit_id: the id of the candidate circuit
        :param candidate: the first hop of the circuit
        :return: Circuit
        """

        self.circuit_id = circuit_id
        self.candidate = candidate
        self.hops = []
        self.goal_hops = goal_hops

        self.extend_strategy = None
        self.last_incoming = time.time()

        self.unverified_hop = None
        """ :type : Hop """

        self.proxy = proxy

    @property
    def online(self):
        """
        Whether the circuit can be considered online, i.e. if it has
        reached it's full length

        @rtype: bool
        """
        return self.goal_hops == len(self.hops)

    @property
    def state(self):
        if self.hops is None:
            return CIRCUIT_STATE_BROKEN

        if len(self.hops) < self.goal_hops:
            return CIRCUIT_STATE_EXTENDING
        else:
            return CIRCUIT_STATE_READY

    @property
    def ping_time_remaining(self):
        too_old = time.time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incoming - too_old
        return diff if diff > 0 else 0

    def __contains__(self, other):
        if isinstance(other, Candidate):
            # TODO: should compare to a list here
            return other == self.candidate

    def beat_heart(self):
        self.last_incoming = time.time()

    @property
    def bytes_downloaded(self):
        return self.proxy.global_stats.circuit_stats[
            self.circuit_id].bytes_downloaded if self.proxy else None

    @property
    def bytes_uploaded(self):
        return self.proxy.global_stats.circuit_stats[
            self.circuit_id].bytes_uploaded if self.proxy else None


class Hop:
    def __init__(self, address, pub_key, dh_first_part):
        self.address = address
        self.pub_key = pub_key
        self.session_key = None
        self.dh_first_part = dh_first_part

    @property
    def host(self):
        return self.address[0]

    @property
    def port(self):
        return self.address[1]

    @staticmethod
    def from_candidate(candidate):
        hop = Hop(candidate.sock_addr, None, None)
        return hop


class TunnelObserver:
    def __init__(self):
        pass

    def on_state_change(self, community, state):
        pass

    def on_incoming_from_tunnel(self, community, circuit_id, origin, data):
        pass

    def on_exiting_from_tunnel(self, circuit_id, candidate, destination, data):
        pass

    def on_tunnel_stats(self, community, candidate, stats):
        pass

    def on_enter_tunnel(self, circuit_id, candidate, origin, payload):
        pass

    def on_send_data(self, circuit_id, candidate, ultimate_destination,
                     payload):
        pass

    def on_relay(self, from_key, to_key, direction, data):
        pass

    def on_unload(self):
        pass


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
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004" \
                     "0460829f9bb72f0cb094904aa6f885ff70e1e98651e81119b1e7" \
                     "b42402f3c5cfa183d8d96738c40ffd909a70020488e3b59b67de" \
                     "57bb1ac5dec351d172fe692555898ac944b68c730590f850ab93" \
                     "1c5732d5a9d573a7fe1f9dc8a9201bc3cb63ab182c9e485d08ff" \
                     "4ac294f09e16d3925930946f87e91ef9c40bbb4189f9c5af6696" \
                     "f57eec3b8f2f77e7ab56fd8d6d63".decode("HEX")

        master = dispersy.get_member(master_key)
        return [master]

    # noinspection PyMethodOverriding
    @classmethod
    def load_community(cls, dispersy, master, my_member, settings=None,
                       integrate_with_tribler=True):
        try:
            dispersy.database.execute(
                u"SELECT 1 FROM community WHERE master = ?",
                (master.database_id,)).next()
        except StopIteration:
            return cls.join_community(
                dispersy, master, my_member, my_member,
                settings, integrate_with_tribler=integrate_with_tribler
            )
        else:
            return super(ProxyCommunity, cls).load_community(
                dispersy, master, settings,
                integrate_with_tribler=integrate_with_tribler
            )

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

    @property
    def crypto(self):
        """
        @rtype: Tribler.community.privatesemantic.crypto.elgamalcrypto.ElgamalCrypto
        """
        return self.dispersy.crypto
    
    def __init__(self, dispersy, master_member, settings=None,
                 integrate_with_tribler=True):
        """
        @type master_member: Tribler.dispersy.member.Member
        """
        self._original_on_introduction_request = None
        self._original_on_introduction_response = None
        Community.__init__(self, dispersy, master_member)

        assert isinstance(master_member, Member)

        if not settings:
            settings = ProxySettings()

        self.lock = threading.RLock()

        # Custom conversion
        self.prefix = "fffffffe".decode("HEX")

        self.proxy_conversion = CustomProxyConversion()
        self.on_custom = defaultdict(lambda: lambda *args: None)
        ''' :type : dict[
            str,
            (
                int, Candidate,
                StatsPayload|Tribler.community.anontunnel.payload.BaseMessage
            ) -> bool]
        '''

        self.on_custom[MESSAGE_CREATE] = self.on_create
        self.on_custom[MESSAGE_CREATED] = self.on_created
        self.on_custom[MESSAGE_DATA] = self.on_data
        self.on_custom[MESSAGE_EXTEND] = self.on_extend
        self.on_custom[MESSAGE_EXTENDED] = self.on_extended
        self.on_custom[MESSAGE_PING] = self.on_ping
        self.on_custom[MESSAGE_PONG] = self.on_pong

        self.__observers = []
        ''' :type : list of TunnelObserver'''


        # Replace endpoint
        dispersy.endpoint.listen_to(self.prefix, self.handle_packet)

        self.circuits = {}
        """ :type : dict[int, Circuit] """
        self.directions = {}

        self.relay_from_to = {}
        """ :type :  dict[((str, int),int),RelayRoute] """

        self.waiting_for = {}
        """ :type :  dict[((str, int),int), bool] """

        self._heartbeat_candidates = {}

        self.key = self.my_member.private_key
        self.session_keys = {}

        sr = random.SystemRandom()
        sys.modules["random"] = sr

        self._send_transformers = {}
        self._receive_transformers = {}
        self._relay_transformers = {}
        self._message_filters = defaultdict(list)

        self.settings = settings

        # Map destination address to the circuit to be used
        self.destination_circuit = {}
        ''' @type: dict[(str, int), int] '''
        self._online = False

        dispersy.callback.register(self.check_ready)
        dispersy.callback.register(self.ping_circuits)

        if integrate_with_tribler:
            from Tribler.Core.CacheDB.Notifier import Notifier

            self.notifier = Notifier.getInstance()
        else:
            self.notifier = None

        # Enable Crypto
        self.settings.crypto.enable(self)

        from Tribler.community.anontunnel.stats import StatsCollector

        self.global_stats = StatsCollector(self)
        self.global_stats.start()

        def loop_discover():
            while True:
                try:
                    yield self.__discover()
                except:
                    yield 5.0

        self.dispersy.callback.register(loop_discover)

    def __discover(self):
        while len(self.circuits) < self.settings.max_circuits:
            logger.debug("Trying to create new circuits")

            goal_hops = self.settings.length_strategy.circuit_length()

            if goal_hops == 0:
                circuit_id = self._generate_circuit_id()
                self.circuits[circuit_id] = Circuit(circuit_id, proxy=self)
            else:
                circuit_candidates = {c.candidate for c in
                                      self.circuits.values()}

                candidates = (c for c
                              in self.dispersy_yield_verified_candidates()
                              if True or c not in circuit_candidates)

                c = next(self.dispersy_yield_verified_candidates(), None)

                if c is None:
                    break
                else:
                    self.create_circuit(c, goal_hops)

        return 5.0


    def add_observer(self, observer):
        #assert isinstance(observer, TunnelObserver)
        self.__observers.append(observer)
        observer.on_state_change(self, self.online)

    def remove_observer(self, observer):
        self.__observers.remove(observer)

    def unload_community(self):
        for o in self.__observers:
            o.on_unload()

        Community.unload_community(self)

    def initiate_conversions(self):
        return [DefaultConversion(self), ProxyConversion(self)]

    def initiate_meta_messages(self):
        return [Message(
            self
            , u"stats"
            , MemberAuthentication()
            , PublicResolution()
            , LastSyncDistribution(synchronization_direction=u"DESC",
                                   priority=128, history_size=1)
            , CommunityDestination(node_count=10)
            , StatsPayload()
            , self.dispersy._generic_timeline_check
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
        self._meta_messages[meta.name] = Message(
            meta.community, meta.name, meta.authentication,
            meta.resolution, meta.distribution, meta.destination,
            meta.payload, meta.check_callback, self.on_introduction_request,
            meta.undo_callback,
            meta.batch
        )

        meta = self._meta_messages[u"dispersy-introduction-response"]
        self._original_on_introduction_response = meta.handle_callback
        self._meta_messages[meta.name] = Message(
            meta.community, meta.name, meta.authentication,
            meta.resolution, meta.distribution, meta.destination,
            meta.payload, meta.check_callback, self.on_introduction_response,
            meta.undo_callback, meta.batch
        )

        assert self._original_on_introduction_request
        assert self._original_on_introduction_response

    def on_introduction_request(self, messages):
        try:
            return self._original_on_introduction_request(messages)
        finally:
            for message in messages:
                self.on_member_heartbeat(message, message.candidate)

    def on_introduction_response(self, messages):
        try:
            return self._original_on_introduction_response(messages)
        finally:
            for message in messages:
                self.on_member_heartbeat(message, message.candidate)

    def on_stats(self, messages):
        for message in messages:
            for o in self.__observers:
                o.on_tunnel_stats(self, message.candidate,
                                  message.payload.stats)

    def get_cached_candidate(self, sock_addr):
        if sock_addr in self._heartbeat_candidates:
            return self._heartbeat_candidates[sock_addr]
        else:
            circuit_candidate = next(
                (c.candidate for c in self.circuits.values() if
                 c.goal_hops > 0 and c.candidate.sock_addr == sock_addr),
                None)
            return circuit_candidate

    def send_stats(self, stats):
        def __send_stats():
            meta = self.get_meta_message(u"stats")
            record = meta.impl(authentication=(self._my_member,),
                               distribution=(self.claim_global_time(),),
                               payload=(stats,))

            logger.warning("Sending stats")
            self.dispersy.store_update_forward([record], True, False, True)

        self.dispersy.callback.register(__send_stats)

    def __handle_incoming(self, circuit_id, am_originator, candidate, data):

        # Transform incoming data using registered transformers
        for f in self._receive_transformers:
            data = f(candidate, circuit_id, data)

        # Try to parse the packet
        _, payload = self.proxy_conversion.decode(data)
        packet_type = self.proxy_conversion.get_type(data)
        str_type = MESSAGE_TYPE_STRING.get(packet_type)

        logger.debug(
            "GOT %s from %s:%d over circuit %d",
            str_type if str_type else 'unknown-type-%d' % ord(packet_type),
            candidate.sock_addr[0],
            candidate.sock_addr[1],
            circuit_id
        )

        # Call any message filter before handing it over to our own handlers
        payload = self._filter_message(circuit_id, candidate,
                                       packet_type, payload, )

        if not payload:
            logger.warning("IGNORED %s from %s:%d over circuit %d",
                           str_type, candidate.sock_addr[0],
                           candidate.sock_addr[1], circuit_id)
            return

        if am_originator:
            self.circuits[circuit_id].beat_heart()

        result = self.on_custom[packet_type](circuit_id, candidate, payload)

        if result:
            self.dict_inc(self.dispersy.statistics.success, str_type)
        else:
            self.dict_inc(self.dispersy.statistics.success, str_type + '-ignored')
            logger.debug("Prev message was IGNORED")


    def __relay(self, circuit_id, data, relay_key, sock_addr):
        # First, relay packet if we know whom to forward message to for
        # this circuit. This happens only when the circuit is already
        # established with both parent and child and if the node is not
        # waiting for a CREATED message from the child

        direction = self.directions[relay_key]
        next_relay = self.relay_from_to[relay_key]

        for f in self._relay_transformers:
            data = f(direction, sock_addr, circuit_id, data)

        this_relay_key = (next_relay.sock_addr, next_relay.circuit_id)

        if this_relay_key in self.relay_from_to:
            this_relay = self.relay_from_to[this_relay_key]
            this_relay.last_incoming = time.time()

            for o in self.__observers:
                # TODO: check whether direction is set correctly here!
                o.on_relay(this_relay_key, next_relay, direction, data)

        packet_type = self.proxy_conversion.get_type(data)

        str_type = MESSAGE_TYPE_STRING.get(
            packet_type, 'unknown-type-%d' % ord(packet_type)
        )

        logger.debug(
            "GOT %s from %s:%d over circuit %d", str_type,
            sock_addr[0], sock_addr[1], circuit_id
        )

        self.send_packet(
            destination=Candidate(next_relay.sock_addr, False),
            circuit_id=next_relay.circuit_id,
            message_type=packet_type,
            packet=data,
            relayed=True
        )

        self.dict_inc(self.dispersy.statistics.success, str_type + '-relayed')

    def handle_packet(self, sock_addr, orig_packet):
        """
        @param (str, int) sock_addr: socket address in tuple format
        @param orig_packet:
        @return:
        """
        packet = orig_packet[len(self.prefix):]
        circuit_id, data = self.proxy_conversion.get_circuit_and_data(packet)
        relay_key = (sock_addr, circuit_id)

        is_relay = circuit_id > 0 and relay_key in self.relay_from_to and \
            not relay_key in self.waiting_for
        is_originator = not is_relay and circuit_id in self.circuits
        is_initial = not is_relay and not is_originator

        try:
            if is_relay:
                return self.__relay(circuit_id, data, relay_key, sock_addr)

            # We don't know this circuit id, so it's the initial message
            # for this circuit
            if is_initial:
                candidate = self.get_cached_candidate(sock_addr)
            else:
                candidate = Candidate(sock_addr, False)

            if not candidate:
                raise Exception("No known candidate at {0}, "
                                "bailing out!".format(sock_addr))

            self.__handle_incoming(circuit_id, is_originator, candidate, data)

        except Exception as e:
            logger.exception(
                "Incoming message could not be handled."
                "connection. INITIAL={0}, ORIGINATOR={1}, RELAY={2}"
                .format(is_initial, is_originator, is_relay))

            if relay_key in self.relay_from_to:
                del self.relay_from_to[relay_key]
            elif circuit_id in self.circuits:
                self.remove_circuit(
                    circuit_id,
                    "Bad crypto, possible old circuit: {0}".format(e.message))
            else:
                logger.debug("Got an encrypted message I can't encrypt. "
                             "Dropping packet, probably old.")

    class CircuitRequestCache(NumberCache):
        @staticmethod
        def create_number(force_number=-1):
            return force_number if force_number >= 0 else NumberCache.create_number()

        @staticmethod
        def create_identifier(number, force_number=-1):
            assert isinstance(number, (int, long)), type(number)
            return u"request-cache:circuit-request:%d" % (number,)

        def __init__(self, community, force_number):
            self.cleanup_delay = 0.0

            NumberCache.__init__(self, community.request_cache, force_number)
            self.community = community

            self.circuit = None
            """ :type : Tribler.community.anontunnel.community.Circuit """

        @property
        def timeout_delay(self):
            return 5.0

        def on_extended(self, extended_message):
            """
            :type extended_message : ExtendedMessage
            """
            unverified_hop = self.circuit.unverified_hop

            session_key = pow(extended_message.key,
                              unverified_hop.dh_first_part,
                              DIFFIE_HELLMAN_MODULUS)
            m = hashlib.sha1()
            m.update(str(session_key))
            key = m.digest()[0:16]

            unverified_hop.session_key = key

            self.circuit.hops.append(unverified_hop)
            self.circuit.unverified_hop = None

            try:
                candidate_list = self.community.decrypt_candidate_list(key,
                                                                       extended_message.candidate_list)
            except Exception as e:
                reason = "Can't decrypt candidate list!"
                logger.exception(reason)
                self.community.remove_circuit(self.circuit.circuit_id, reason)
                return

            dispersy = self.community.dispersy
            if dispersy.lan_address in candidate_list:
                del candidate_list[dispersy.lan_address]

            if dispersy.wan_address in candidate_list:
                del candidate_list[dispersy.wan_address]

            for hop in self.circuit.hops:
                if hop.address in candidate_list:
                    del candidate_list[hop.address]

            if self.circuit.state == CIRCUIT_STATE_EXTENDING:
                try:
                    self.circuit.extend_strategy.extend(candidate_list)
                except ValueError as e:
                    logger.exception("Cannot extend due to exception:")
                    reason = 'extend error on CircuitRequestCache, state = %s' % self.circuit.state
                    self.community.remove_circuit(self.number, reason)

            elif self.circuit.state == CIRCUIT_STATE_READY:
                self.on_success()

            if self.community.notifier:
                from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, \
                    NTFY_CREATED, NTFY_EXTENDED

                if len(self.circuit.hops) == 1:
                    self.community.notifier.notify(NTFY_ANONTUNNEL,
                                                   NTFY_CREATED, self.circuit)
                else:
                    self.community.notifier.notify(NTFY_ANONTUNNEL,
                                                   NTFY_EXTENDED, self.circuit)

        def on_success(self):
            if self.circuit.state == CIRCUIT_STATE_READY:
                logger.info("Circuit %d is ready", self.number)
                self.community.dispersy.callback.register(
                    self.community.request_cache.pop, args=(self.identifier,))

        def on_timeout(self):
            if not self.circuit.state == CIRCUIT_STATE_READY:
                reason = 'timeout on CircuitRequestCache, state = %s' % self.circuit.state
                self.community.remove_circuit(self.number, reason)

    def create_circuit(self, first_hop, goal_hops, extend_strategy=None):
        """ Create a new circuit, with one initial hop

        @param first_hop: The first hop of our circuit, needs to be
            a candidate.
        @param goal_hops: The number of hops the circuit should reach
        @param extend_strategy: The extend strategy used

        @type first_hop: WalkCandidate
        @type goal_hops: int
        @type extend_strategy: T <= extendstrategies.ExtendStrategy
        """
        try:
            circuit_id = self._generate_circuit_id(first_hop.sock_addr)

            cache = self._request_cache.add(
                ProxyCommunity.CircuitRequestCache(self, circuit_id))

            circuit = cache.circuit = Circuit(
                circuit_id=circuit_id,
                goal_hops=goal_hops,
                candidate=first_hop,
                proxy=self)


            circuit.extend_strategy = extend_strategy if extend_strategy else \
             self.settings.extend_strategy(self, circuit)

            pub_key = iter(first_hop.get_members()).next()._ec

            dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)
            while dh_secret >= DIFFIE_HELLMAN_MODULUS:
                dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)

            dh_first_part = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                                DIFFIE_HELLMAN_MODULUS)

            encrypted_dh_first_part = self.crypto.encrypt(
                pub_key, int_to_packed(dh_first_part, 2048))

            circuit.unverified_hop = Hop(first_hop.sock_addr,
                                         pub_key,
                                         dh_secret)
            logger.info(
                'Circuit %d is to be created, wants %d hops sending to %s:%d',
                circuit_id, circuit.goal_hops,
                first_hop.sock_addr[0],
                first_hop.sock_addr[1]
            )

            self.circuits[circuit_id] = circuit
            self.waiting_for[(first_hop.sock_addr, circuit_id)] = True
            self.send_message(first_hop, circuit_id, MESSAGE_CREATE,
                              CreateMessage(encrypted_dh_first_part))

            return circuit
        except Exception as e:
            logger.exception("create_circuit")

    def remove_circuit(self, circuit_id, additional_info=''):
        assert isinstance(circuit_id, (long, int)), type(circuit_id)

        if circuit_id in self.circuits:
            logger.error("Breaking circuit %d " + additional_info, circuit_id)

            del self.circuits[circuit_id]

            return True
        return False

    def remove_relay(self, relay_key, additional_info=''):
        if relay_key in self.relay_from_to:
            logger.error(
                ("Breaking relay %s:%d %d " + additional_info) % (
                    relay_key[0][0], relay_key[0][1], relay_key[1]))

            # Only remove one side of the relay, this isn't as pretty but
            # both sides have separate incoming timer, hence
            # after removing one side the other will follow.
            del self.relay_from_to[relay_key]
            return True
        return False

    def on_create(self, circuit_id, candidate, message):
        """
        Handle incoming CREATE message, acknowledge the CREATE request with a
        CREATED reply

        @param int circuit_id: The circuit's identifier
        @param Candidate candidate: The candidate we got a CREATE message from
        @param CreateMessage message: The message's payload
        """
        logger.info('We joined circuit %d with neighbour %s', circuit_id,
                    candidate)

        relay_key = (candidate.sock_addr, circuit_id)
        self.directions[relay_key] = ENDPOINT

        dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)
        while dh_secret >= DIFFIE_HELLMAN_MODULUS:
            dh_secret = random.getrandbits(DIFFIE_HELLMAN_MODULUS_SIZE)

        my_key = self.my_member._ec

        decrypted_dh_first_part = packed_to_int(
            self.crypto.decrypt(my_key, message.key), 2048)

        key = pow(decrypted_dh_first_part, dh_secret, DIFFIE_HELLMAN_MODULUS)

        m = hashlib.sha1()
        m.update(str(key))
        key = m.digest()[0:16]

        self.session_keys[relay_key] = key
        #logger.debug("The create message's key   : {}".format(message.key))
        #logger.debug("My diffie secret           : {}".format(self.dh_secret))
        #logger.debug("SECRET {} FOR THE ORIGINATOR NODE".format(key))

        return_key = pow(DIFFIE_HELLMAN_GENERATOR, dh_secret,
                         DIFFIE_HELLMAN_MODULUS)

        cand_dict = {}
        for i in range(1, 5):
            candidate_temp = next(self.dispersy_yield_verified_candidates(), None)
            if not candidate_temp:
                break
            # first member of candidate contains elgamal key
            ec_key = iter(candidate_temp.get_members()).next()._ec

            key_string = self.crypto.key_to_bin(ec_key)

            cand_dict[candidate_temp.sock_addr] = key_string
            logger.debug("Found candidate {0} with key".format(
                    candidate_temp.sock_addr))

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_JOINED

            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_JOINED,
                                 candidate.sock_addr, circuit_id)

        index = (candidate.sock_addr, circuit_id)
        encrypted_cand_dict = self.encrypt_candidate_list(
            self.session_keys[index], cand_dict)

        return self.send_message(
            destination=candidate,
            circuit_id=circuit_id,
            message_type=MESSAGE_CREATED,
            message=CreatedMessage(return_key, encrypted_cand_dict)
        )

    @staticmethod
    def encrypt_candidate_list(key, cand_dict):
        encoded_dict = encoding.encode(cand_dict)
        return crypto.aes_encode(key, encoded_dict)

    @staticmethod
    def decrypt_candidate_list(key, encrypted_cand_dict):
        encoded_dict = crypto.aes_decode(key, encrypted_cand_dict)
        offset, cand_dict = encoding.decode(encoded_dict)
        return cand_dict

    def on_created(self, circuit_id, candidate, message):
        """ Handle incoming CREATED messages relay them backwards towards
        the originator if necessary

        @param int circuit_id: The circuit's id we got a CREATED message on
        @param Candidate candidate: The candidate we got the message from
        @param CreatedMessage message: The message we received

        """
        relay_key = (candidate.sock_addr, circuit_id)

        del self.waiting_for[relay_key]
        self.directions[relay_key] = ORIGINATOR
        if relay_key in self.relay_from_to:
            logger.debug("Got CREATED message, forward as EXTENDED to origin.")
            extended_message = ExtendedMessage(message.key,
                                               message.candidate_list)
            forwarding_relay = self.relay_from_to[relay_key]

            candidate = Candidate(forwarding_relay.sock_addr, False)
            return self.send_message(candidate, forwarding_relay.circuit_id,
                                     MESSAGE_EXTENDED, extended_message)

        request = self.dispersy.callback.call(
            self.request_cache.get,
            args=(self.CircuitRequestCache.create_identifier(circuit_id),))

        if request:
            request.on_extended(message)
            return True

        return False

    def on_data(self, circuit_id, candidate, message):
        """ Handles incoming DATA message, forwards it over the chain or over the internet if needed."""
        if circuit_id in self.circuits \
                and message.destination == ("0.0.0.0", 0) \
                and candidate == self.circuits[circuit_id].candidate:

            self.circuits[circuit_id].last_incoming = time.time()
            #self.circuits[circuit_id].bytes_down[1] += len(message.data)

            for observer in self.__observers:
                observer.on_incoming_from_tunnel(self, circuit_id,
                                                 message.origin, message.data)

            return True

        # If it is not ours and we have nowhere to forward to then act as exit node
        if message.destination != ('0.0.0.0', 0):
            for observer in self.__observers:
                observer.on_exiting_from_tunnel(circuit_id, candidate,
                                                message.destination,
                                                message.data)

            return True
        return False

    def on_extend(self, circuit_id, candidate, message):
        """ Upon reception of a EXTEND message the message
            is forwarded over the Circuit if possible. At the end of
            the circuit a CREATE request is send to the Proxy to
            extend the circuit with. It's CREATED reply will
            eventually be received and propagated back along the Circuit. """

        if message.extend_with:
            extend_with_addr = message.extend_with
            logger.warning(
                "We might be sending a CREATE to someone we don't know, sending to %s:%d!",
                message.host,
                message.port)
        else:
            extend_with_addr = next(
                (x.sock_addr for x in self.dispersy_yield_verified_candidates()
                 if x and x != candidate),
                None
            )

        if not extend_with_addr:
            return

        relay_key = (candidate.sock_addr, circuit_id)
        if relay_key in self.relay_from_to:
            current_relay = self.relay_from_to[relay_key]
            assert not current_relay.online, "shouldn't be called whenever relay is online, the extend message should have been forwarded"

            # We will just forget the attempt and try again, possible with another candidate
            old_to_key = current_relay.sock_addr, current_relay.circuit_id
            del self.relay_from_to[old_to_key]
            del self.relay_from_to[relay_key]

        new_circuit_id = self._generate_circuit_id(extend_with_addr)
        to_key = (extend_with_addr, new_circuit_id)

        self.waiting_for[to_key] = True
        self.relay_from_to[to_key] = RelayRoute(circuit_id,
                                                candidate.sock_addr)
        self.relay_from_to[relay_key] = RelayRoute(new_circuit_id,
                                                   extend_with_addr)

        key = message.key

        self.directions[to_key] = ORIGINATOR
        self.directions[relay_key] = ENDPOINT

        extend_candidate = self.get_cached_candidate(extend_with_addr)
        return self.send_message(extend_candidate, new_circuit_id,
                                 MESSAGE_CREATE, CreateMessage(key))

    def on_extended(self, circuit_id, candidate, message):
        """ A circuit has been extended, forward the acknowledgment back
            to the origin of the EXTEND. If we are the origin update
            our records. """

        request = self.dispersy.callback.call(
            self._request_cache.get,
            args=(ProxyCommunity.CircuitRequestCache.create_identifier(circuit_id),))

        if request:
            request.on_extended(message)
            return True
        return False

    class PingRequestCache(NumberCache):

        @staticmethod
        def create_number(force_number=-1):
            return force_number if force_number >= 0 else NumberCache.create_number()

        @staticmethod
        def create_identifier(number, force_number=-1):
            assert isinstance(number, (int, long)), type(number)
            return u"request-cache:ping-request:%d" % (number,)

        def __init__(self, community, force_number):
            NumberCache.__init__(self, community.request_cache, force_number)
            self.community = community

        @property
        def timeout_delay(self):
            return 5.0

        @property
        def cleanup_delay(self):
            return 0.0

        def on_pong(self):
            self.community.dispersy.callback.register(
                self.community.request_cache.pop, args=(self.identifier,))

        def on_timeout(self):
            self.community.remove_circuit(self.number,
                                          'timeout on PingRequestCache')

    def create_ping(self, candidate, circuit_id):
        self._dispersy.callback.register(self._request_cache.add,
                                         args=(
                                             ProxyCommunity.PingRequestCache(
                                                 self,
                                                 circuit_id),))
        self.send_message(candidate, circuit_id, MESSAGE_PING, PingMessage())

    def on_ping(self, circuit_id, candidate, message):
        logger.debug("GOT PING FROM CIRCUIT {0}".format(circuit_id))
        if circuit_id in self.circuits:
            return self.send_message(candidate, circuit_id, MESSAGE_PONG,
                                     PongMessage())
        return False

    def on_pong(self, circuit_id, candidate, message):
        logger.debug("GOT PONG FROM CIRCUIT {0}".format(circuit_id))
        request = self.dispersy.callback.call(self._request_cache.get,
                                              args=(
                                                  ProxyCommunity.PingRequestCache.create_identifier(
                                                      circuit_id),))
        if request:
            request.on_pong(message)
            return True
        return False

    # got introduction_request or introduction_response from candidate
    # not necessarily a new candidate
    def on_member_heartbeat(self, message, candidate):
        if not isinstance(candidate, WalkCandidate) or isinstance(candidate,
                                                                  BootstrapCandidate):
            return

        candidate._associations.clear()
        candidate.associate(message.authentication.member)
        self._heartbeat_candidates[candidate.sock_addr] = candidate

        # if len(self.circuits) < self.settings.max_circuits and candidate not in [c.candidate for c in self.circuits.values()]:
        #     self.create_circuit(candidate, self.settings.length_strategy.circuit_length())

    def _generate_circuit_id(self, neighbour=None):
        circuit_id = random.randint(1, 255000)

        # prevent collisions
        while circuit_id in self.circuits or (
                    neighbour and (
                        neighbour, circuit_id) in self.relay_from_to):
            circuit_id = random.randint(1, 255000)

        return circuit_id

    def add_receive_transformer(self, func):
        self._receive_transformers[func] = 1

    def remove_receive_transformer(self, func):
        if func in self._receive_transformers:
            del self._receive_transformers[func]

    def add_relay_transformer(self, func):
        self._relay_transformers[func] = 1

    def remove_relay_transformer(self, func):
        if func in self._relay_transformers:
            del self._relay_transformers[func]

    def add_send_transformer(self, func):
        self._send_transformers[func] = 1

    def remove_send_transformer(self, func):
        if func in self._send_transformers:
            del self._send_transformers[func]

    def _filter_message(self, candidate, circuit_id, message_type, payload):
        for f in self._message_filters[message_type]:
            payload = f(candidate, circuit_id, payload)

            if not payload:
                return None

        return payload

    def remove_message_filter(self, message_type, filter_func):
        self._message_filters[message_type].remove(filter_func)

    def add_message_filter(self, message_type, filter_func):
        self._message_filters[message_type].append(filter_func)

    def send_message(self, destination, circuit_id, message_type, message):
        content = self.proxy_conversion.encode(message_type, message)

        for transformer in self._send_transformers.keys():
            content = transformer(destination, circuit_id, message_type,
                                  content)

        return self.send_packet(destination, circuit_id, message_type, content)

    def send_packet(self, destination, circuit_id, message_type, packet,
                    relayed=False):
        assert isinstance(destination, Candidate), type(destination)
        assert isinstance(packet, str), type(packet)

        packet = self.proxy_conversion.add_circuit(packet, circuit_id)

        str_type = MESSAGE_TYPE_STRING.get(
            message_type, "unknown-type-" + str(ord(message_type)))

        logger.debug(
            "SEND %s to %s:%d over circuit %d",
            str_type,
            destination.sock_addr[0], destination.sock_addr[1],
            circuit_id)

        self.dict_inc(self.dispersy.statistics.outgoing,
                      str_type + ('-relayed' if relayed else ''), 1)

        # we need to make sure that this endpoint is thread safe
        return self.dispersy.endpoint.send([destination],
                                           [self.prefix + packet])

    def dict_inc(self, statistics_dict, key, inc=1):
        self._dispersy.statistics.dict_inc(statistics_dict,
                                           u"anontunnel-" + key, inc)

    # CIRCUIT STUFFS
    def get_circuits(self):
        return self.circuits.values()

    @property
    def active_circuits(self):
        # Circuit is active when its state is CIRCUIT_STATE_READY
        return {circuit_id: circuit
                for circuit_id, circuit in self.circuits.items()
                if circuit.state == CIRCUIT_STATE_READY}

    def check_ready(self):
        while True:
            try:
                self.online = self.settings.select_strategy.can_select(
                    self.active_circuits)
            except:
                logger.exception("Can_select should not raise any exceptions!")
                self.online = False

            yield 1.0

    def ping_circuits(self):
        while True:
            try:
                to_be_removed = [self.remove_relay(relay_key, 'no activity')
                                 for relay_key, relay
                                 in self.relay_from_to.items()
                                 if relay.ping_time_remaining == 0]

                logger.info("removed %d relays", len(to_be_removed))
                assert all(to_be_removed)

                to_be_pinged = [circuit
                                for circuit in self.circuits.values()
                                if circuit.ping_time_remaining < PING_INTERVAL and circuit.candidate]

                logger.info("pinging %d circuits", len(to_be_pinged))
                for circuit in to_be_pinged:
                    self.create_ping(circuit.candidate, circuit.circuit_id)
            except:
                logger.exception("Ping error")

            yield PING_INTERVAL

    def unlink_destinations(self, destinations):
        with self.lock:
            for destination in destinations:
                if destination in self.destination_circuit:
                    del self.destination_circuit[destination]

    def __select_circuit(self, ultimate_destination):
        circuit_id = self.destination_circuit.get(ultimate_destination, None)

        if circuit_id in self.active_circuits:
            return self.active_circuits[circuit_id]
        else:
            strategy = self.settings.select_strategy
            circuit_id = strategy.select(self.active_circuits.values()).circuit_id
            self.destination_circuit[ultimate_destination] = circuit_id

            logger.warning("SELECT circuit %d with length %d for %s:%d",
                            circuit_id,
                            self.circuits[circuit_id].goal_hops,
                            *ultimate_destination)

            return self.active_circuits[circuit_id]

    def __notify(self, method, *args, **kwargs):
        for o in self.__observers:
            method(o, *args, **kwargs)

    def tunnel_data_to_end(self, ultimate_destination, payload):
        with self.lock:
            circuit = self.__select_circuit(ultimate_destination)

            if circuit.goal_hops == 0:
                self.__notify(
                    TunnelObserver.on_exiting_from_tunnel,
                    circuit.circuit_id, None, ultimate_destination, payload)
            else:
                self.send_message(circuit.candidate, circuit.circuit_id,
                                  MESSAGE_DATA,
                                  DataMessage(ultimate_destination,
                                              payload, None))

                self.__notify(
                    TunnelObserver.on_send_data,
                    circuit.circuit_id, circuit.candidate,
                    ultimate_destination, payload)

    def enter_data(self, circuit_id, candidate, source_address, payload):
        with self.lock:
            self.send_message(candidate, circuit_id, MESSAGE_DATA,
                              DataMessage(None, payload, source_address))
            self.__notify(
                TunnelObserver.on_enter_tunnel,
                circuit_id, candidate, source_address, payload)