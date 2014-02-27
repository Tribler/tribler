"""
AnonTunnel community module
"""

# Python imports
import sys
import threading
import random
import time
from collections import defaultdict

# Tribler and Dispersy imports
from twisted.internet import defer
from Tribler.community.anontunnel.cache import CircuitRequestCache, \
    PingRequestCache
from Tribler.community.anontunnel.routing import Circuit, Hop, RelayRoute
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.candidate import Candidate, WalkCandidate, \
    BootstrapCandidate
from Tribler.dispersy.community import Community

# AnonTunnel imports
from Tribler.community.anontunnel import crypto
from Tribler.community.anontunnel import extendstrategies
from Tribler.community.anontunnel import selectionstrategies
from Tribler.community.anontunnel import lengthstrategies
from Tribler.community.anontunnel.payload import StatsPayload, CreateMessage, \
    CreatedMessage, ExtendedMessage, \
    PongMessage, PingMessage, DataMessage
from Tribler.community.anontunnel.conversion import CustomProxyConversion, \
    ProxyConversion
from Tribler.community.anontunnel.globals import MESSAGE_EXTEND, \
    MESSAGE_CREATE, MESSAGE_CREATED, MESSAGE_DATA, MESSAGE_EXTENDED, \
    MESSAGE_PING, MESSAGE_PONG, MESSAGE_TYPE_STRING, \
    CIRCUIT_STATE_READY, CIRCUIT_STATE_EXTENDING, \
    ORIGINATOR, PING_INTERVAL, ENDPOINT

__author__ = 'chris'

import logging


class ProxySettings:
    """
    Data structure containing settings, including some defaults,
    for the ProxyCommunity
    """

    def __init__(self):
        length = random.randint(1, 3)

        self.max_circuits = 4
        self.extend_strategy = extendstrategies.NeighbourSubset
        self.select_strategy = selectionstrategies.RoundRobin()
        self.length_strategy = lengthstrategies.ConstantCircuitLength(length)
        self.crypto = crypto.DefaultCrypto()


class ProxyCommunity(Community):
    """
    The dispersy community which discovers other proxies on the internet and
    creates TOR-like circuits together with them

    @type dispersy: Tribler.dispersy.dispersy.Dispersy
    @type master_member: Tribler.dispersy.member.Member
    @type settings: ProxySettings or unknown
    @type integrate_with_tribler: bool
    """

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Wed Sep 18 22:47:22 2013
        # curve: high <<< NID_sect571r1 >>>
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000404608
        # 29f9bb72f0cb094904aa6f885ff70e1e98651e81119b1e7b42402f3c5cfa183d8d
        # 96738c40ffd909a70020488e3b59b67de57bb1ac5dec351d172fe692555898ac94
        # 4b68c730590f850ab931c5732d5a9d573a7fe1f9dc8a9201bc3cb63ab182c9e485
        # d08ff4ac294f09e16d3925930946f87e91ef9c40bbb4189f9c5af6696f57eec3b8
        # f2f77e7ab56fd8d6d63
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
    def crypto(self):
        """
        @rtype: ElgamalCrypto
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

        self.lock = threading.RLock()
        self._logger = logging.getLogger(__name__)

        self.settings = settings if settings else ProxySettings()
        # Custom conversion
        self.__packet_prefix = "fffffffe".decode("HEX")

        self.observers = []
        ''' :type : list of TunnelObserver'''

        self.proxy_conversion = CustomProxyConversion()
        self._message_handlers = defaultdict(lambda: lambda *args: None)
        ''' :type : dict[
            str,
            (
                int, Candidate,
                StatsPayload|Tribler.community.anontunnel.payload.BaseMessage
            ) -> bool]
        '''

        self.circuits = {}
        """ :type : dict[int, Circuit] """
        self.directions = {}

        self.relay_from_to = {}
        """ :type :  dict[((str, int),int),RelayRoute] """

        self.waiting_for = {}
        """ :type :  dict[((str, int),int), bool] """

        self._heartbeat_candidates = {}

        self.key = self.my_member.private_key

        sys.modules["random"] = random.SystemRandom()

        self.send_transformers = []
        self.receive_transformers = []
        ''' @type: dict[,(Candidate, int, str) -> ] '''
        self.relay_transformers = []
        self.before_send_transformers = defaultdict(list)
        self.after_receive_transformers = defaultdict(list)

        # Map destination address to the circuit to be used
        self.destination_circuit = {}
        ''' @type: dict[(str, int), int] '''

        self._circuit_promises = []
        self._reservations = set()

        # Attach message handlers
        self._initiate_message_handlers()

        # Enable Crypto
        self.settings.crypto.enable(self)

        # Enable global counters
        from Tribler.community.anontunnel.stats import StatsCollector

        self.global_stats = StatsCollector(self)
        self.global_stats.start()

        # Listen to prefix endpoint
        dispersy.endpoint.listen_to(self.__packet_prefix, self.__handle_packet)
        dispersy.callback.register(self.__ping_circuits)

        if integrate_with_tribler:
            from Tribler.Core.CacheDB.Notifier import Notifier

            self.notifier = Notifier.getInstance()
        else:
            self.notifier = None

        def __loop_discover():
            while True:
                try:
                    self.__discover()
                finally:
                    yield 5.0

        self.dispersy.callback.register(__loop_discover)

    def __discover(self):
        circuits_needed = lambda: max(
            len(self._circuit_promises),
            self.settings.max_circuits - len(self.circuits)
        )

        with self.lock:
            while circuits_needed():
                self._logger.debug("Need %d new circuits!", circuits_needed())
                goal_hops = self.settings.length_strategy.circuit_length()

                if goal_hops == 0:
                    deferred = self._circuit_promises.pop(0) if \
                        len(self._circuit_promises) else None

                    circuit_id = self._generate_circuit_id()
                    self.circuits[circuit_id] = Circuit(
                        circuit_id=circuit_id,
                        proxy=self,
                        deferred=deferred)
                else:
                    circuit_candidates = {c.candidate for c in
                                          self.circuits.values()}

                    candidates = (c for c
                                  in self.dispersy_yield_verified_candidates()
                                  if c not in circuit_candidates)

                    c = next(candidates, None)

                    if c is None:
                        break
                    else:
                        deferred = self._circuit_promises.pop(0) if \
                            len(self._circuit_promises) else None
                        self._create_circuit(c, goal_hops, deferred=deferred)

    def unload_community(self):
        """
        Called by dispersy when the ProxyCommunity is being unloaded
        @return:
        """
        self.__notify('on_unload')
        Community.unload_community(self)

    def _initiate_message_handlers(self):
        self._message_handlers[MESSAGE_CREATE] = self.on_create
        self._message_handlers[MESSAGE_CREATED] = self.on_created
        self._message_handlers[MESSAGE_DATA] = self.on_data
        self._message_handlers[MESSAGE_EXTEND] = self.on_extend
        self._message_handlers[MESSAGE_EXTENDED] = self.on_extended
        self._message_handlers[MESSAGE_PING] = self.on_ping
        self._message_handlers[MESSAGE_PONG] = self.on_pong

    def initiate_conversions(self):
        """
        Called by dispersy when we need to return our message Conversions
        @rtype: list[Tribler.dispersy.conversion.Conversion]
        """
        return [DefaultConversion(self), ProxyConversion(self)]

    def initiate_meta_messages(self):
        """
        Called by dispersy when we need to define the messages we would like
        to use in the community
        @rtype: list[Message]
        """
        return [Message(
            self,
            u"stats",
            MemberAuthentication(),
            PublicResolution(),
            LastSyncDistribution(synchronization_direction=u"DESC",
                                 priority=128, history_size=1),
            CommunityDestination(node_count=10),
            StatsPayload(),
            self.dispersy._generic_timeline_check,
            self._on_stats
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
            meta.payload, meta.check_callback, self.__on_introduction_request,
            meta.undo_callback,
            meta.batch
        )

        meta = self._meta_messages[u"dispersy-introduction-response"]
        self._original_on_introduction_response = meta.handle_callback
        self._meta_messages[meta.name] = Message(
            meta.community, meta.name, meta.authentication,
            meta.resolution, meta.distribution, meta.destination,
            meta.payload, meta.check_callback, self.__on_introduction_response,
            meta.undo_callback, meta.batch
        )

        assert self._original_on_introduction_request
        assert self._original_on_introduction_response

    def __on_introduction_request(self, messages):
        try:
            return self._original_on_introduction_request(messages)
        finally:
            for message in messages:
                self.__on_member_heartbeat(message, message.candidate)

    def __on_introduction_response(self, messages):
        try:
            return self._original_on_introduction_response(messages)
        finally:
            for message in messages:
                self.__on_member_heartbeat(message, message.candidate)

    def _on_stats(self, messages):
        for message in messages:
            self.__notify("on_tunnel_stats",
                          self, message.candidate, message.payload.stats)

    def _get_cached_candidate(self, sock_addr):
        if sock_addr in self._heartbeat_candidates:
            return self._heartbeat_candidates[sock_addr]
        else:
            circuit_candidate = next(
                (c.candidate for c in self.circuits.values() if
                 c.goal_hops > 0 and c.candidate.sock_addr == sock_addr),
                None)
            return circuit_candidate

    def send_stats(self, stats):
        """
        Send a stats message to the community
        @param dict stats: the statistics dictionary to share
        """

        def __send_stats():
            meta = self.get_meta_message(u"stats")
            record = meta.impl(authentication=(self._my_member,),
                               distribution=(self.claim_global_time(),),
                               payload=(stats,))

            self._logger.warning("Sending stats")
            self.dispersy.store_update_forward([record], True, False, True)

        self.dispersy.callback.register(__send_stats)

    def __handle_incoming(self, circuit_id, am_originator, candidate, data):
        # Transform incoming data using registered transformers
        for f in self.receive_transformers:
            data = f(candidate, circuit_id, data)

        # Try to parse the packet
        _, payload = self.proxy_conversion.decode(data)

        packet_type = self.proxy_conversion.get_type(data)
        str_type = MESSAGE_TYPE_STRING.get(packet_type)

        # Call any msg transformer before handing it over to our own handlers
        for transformer in self.after_receive_transformers[packet_type]:
            payload = transformer(candidate, circuit_id, payload)
            if not payload:
                return None

        self._logger.debug(
            "GOT %s from %s:%d over circuit %d",
            str_type if str_type else 'unknown-type-%d' % ord(packet_type),
            candidate.sock_addr[0],
            candidate.sock_addr[1],
            circuit_id
        )

        if not payload:
            self._logger.warning("IGNORED %s from %s:%d over circuit %d",
                                 str_type, candidate.sock_addr[0],
                                 candidate.sock_addr[1], circuit_id)
            return

        if am_originator:
            self.circuits[circuit_id].beat_heart()

        handler = self._message_handlers[packet_type]
        result = handler(circuit_id, candidate, payload)

        if result:
            self.__dict_inc(self.dispersy.statistics.success, str_type)
        else:
            self.__dict_inc(self.dispersy.statistics.success,
                            str_type + '-ignored')
            self._logger.debug("Prev message was IGNORED")

    def __relay(self, circuit_id, data, relay_key, sock_addr):
        # First, relay packet if we know whom to forward message to for
        # this circuit. This happens only when the circuit is already
        # established with both parent and child and if the node is not
        # waiting for a CREATED message from the child

        direction = self.directions[relay_key]
        next_relay = self.relay_from_to[relay_key]

        for transformer in self.relay_transformers:
            data = transformer(direction, sock_addr, circuit_id, data)

        this_relay_key = (next_relay.sock_addr, next_relay.circuit_id)

        if this_relay_key in self.relay_from_to:
            this_relay = self.relay_from_to[this_relay_key]
            this_relay.last_incoming = time.time()

            # TODO: check whether direction is set correctly here!
            self.__notify("on_relay",
                          this_relay_key, relay_key, direction, data)

        packet_type = self.proxy_conversion.get_type(data)

        str_type = MESSAGE_TYPE_STRING.get(
            packet_type, 'unknown-type-%d' % ord(packet_type)
        )

        self._logger.debug(
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

        self.__dict_inc(self.dispersy.statistics.success,
                        str_type + '-relayed')

    def __handle_packet(self, sock_addr, orig_packet):
        """
        @param (str, int) sock_addr: socket address in tuple format
        @param orig_packet:
        @return:
        """
        packet = orig_packet[len(self.__packet_prefix):]
        circuit_id, data = self.proxy_conversion.get_circuit_and_data(packet)
        relay_key = (sock_addr, circuit_id)

        is_relay = circuit_id > 0 and relay_key in self.relay_from_to \
            and not relay_key in self.waiting_for
        is_originator = not is_relay and circuit_id in self.circuits
        is_initial = not is_relay and not is_originator

        try:
            if is_relay:
                return self.__relay(circuit_id, data, relay_key, sock_addr)

            candidate = self._get_cached_candidate(sock_addr)
            if not candidate:
                self._logger.error("Unknown candidate at %s, drop!", sock_addr)
                return

            self.__handle_incoming(circuit_id, is_originator, candidate, data)
        except:
            self._logger.exception(
                "Incoming from {3} on {4} message error."
                "INITIAL={0}, ORIGINATOR={1}, RELAY={2}"
                .format(is_initial, is_originator, is_relay, sock_addr,
                        circuit_id))

            if relay_key in self.relay_from_to:
                self.remove_relay(relay_key, "error on incoming packet!")
            elif circuit_id in self.circuits:
                self.remove_circuit(circuit_id, "error on incoming packet!")

    def _create_circuit(self, first_hop, goal_hops, extend_strategy=None,
                        deferred=None):
        """ Create a new circuit, with one initial hop

        @param WalkCandidate first_hop: The first hop of our circuit, needs to
            be a candidate.
        @param int goal_hops: The number of hops the circuit should reach
        @param T <= extendstrategies.ExtendStrategy extend_strategy:
        The extend strategy used

        @rtype: Tribler.community.anontunnel.routing.Circuit
        """
        try:
            circuit_id = self._generate_circuit_id(first_hop.sock_addr)

            cache = self._request_cache.add(
                CircuitRequestCache(self, circuit_id))

            circuit = cache.circuit = Circuit(
                circuit_id=circuit_id,
                goal_hops=goal_hops,
                candidate=first_hop,
                deferred=deferred,
                proxy=self)

            if extend_strategy:
                circuit.extend_strategy = extend_strategy
            else:
                circuit.extend_strategy = self.settings.extend_strategy(
                    self, circuit)

            circuit.unverified_hop = Hop(first_hop.sock_addr)

            self._logger.info(
                'Circuit %d is to be created, wants %d hops sending to %s:%d',
                circuit_id, circuit.goal_hops,
                first_hop.sock_addr[0],
                first_hop.sock_addr[1]
            )

            self.circuits[circuit_id] = circuit
            self.waiting_for[(first_hop.sock_addr, circuit_id)] = True
            self.send_message(first_hop, circuit_id, MESSAGE_CREATE,
                              CreateMessage())

            return circuit
        except Exception:
            self._logger.exception("create_circuit")

    def remove_circuit(self, circuit_id, additional_info=''):
        """
        Removes a circuit from our pool, destroying it
        @param int circuit_id: the id of the circuit to destroy
        @param str additional_info: optional reason, useful for logging
        @return: whether the removal was successful
        """
        assert isinstance(circuit_id, (long, int)), type(circuit_id)

        if circuit_id in self.circuits:
            self._logger.error("Breaking circuit %d " + additional_info,
                               circuit_id)
            circuit = self.circuits[circuit_id]

            circuit.destroy()
            del self.circuits[circuit_id]
            self.__notify("on_break_circuit", circuit)

            return True
        return False

    def remove_relay(self, relay_key, additional_info=''):
        """
        Removes a relay from our routing table, will drop any incoming packets
        and eventually cause a timeout at the originator

        @param ((str, int) int) relay_key: the key of the relay to remove
        @param str additional_info: optional reason, useful for logging
        @return: whether the removal was successful
        """
        if relay_key in self.relay_from_to:
            self._logger.error(
                ("Breaking relay %s:%d %d " + additional_info) % (
                    relay_key[0][0], relay_key[0][1], relay_key[1]))

            # Only remove one side of the relay, this isn't as pretty but
            # both sides have separate incoming timer, hence
            # after removing one side the other will follow.
            del self.relay_from_to[relay_key]

            self.__notify("on_break_relay", relay_key)
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
        relay_key = (candidate.sock_addr, circuit_id)
        self.directions[relay_key] = ENDPOINT
        self._logger.info('We joined circuit %d with neighbour %s'
                          , circuit_id, candidate)

        candidate_dict = {}
        for _ in range(1, 5):
            candidate_temp = next(self.dispersy_yield_verified_candidates(),
                                  None)
            if not candidate_temp:
                break
            # first member of candidate contains elgamal key
            ec_key = iter(candidate_temp.get_members()).next()._ec

            key_string = self.crypto.key_to_bin(ec_key)

            candidate_dict[candidate_temp.sock_addr] = key_string
            self._logger.debug("Found candidate {0} with key".format(
                candidate_temp.sock_addr))

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_JOINED

            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_JOINED,
                                 candidate.sock_addr, circuit_id)

        return self.send_message(
            destination=candidate,
            circuit_id=circuit_id,
            message_type=MESSAGE_CREATED,
            message=CreatedMessage(candidate_dict)
        )

    def on_created(self, circuit_id, candidate, message):
        """ Handle incoming CREATED messages relay them backwards towards
        the originator if necessary

        @param int circuit_id: The circuit's id we got a CREATED message on
        @param Candidate candidate: The candidate we got the message from
        @param CreatedMessage message: The message we received

        @return: whether the message could be handled correctly

        """
        relay_key = (candidate.sock_addr, circuit_id)

        del self.waiting_for[relay_key]
        self.directions[relay_key] = ORIGINATOR
        if relay_key in self.relay_from_to:
            self._logger.debug("Got CREATED message, "
                               "forward as EXTENDED to origin.")
            extended_message = ExtendedMessage(message.key,
                                               message.candidate_list)
            forwarding_relay = self.relay_from_to[relay_key]

            candidate = Candidate(forwarding_relay.sock_addr, False)
            return self.send_message(candidate, forwarding_relay.circuit_id,
                                     MESSAGE_EXTENDED, extended_message)

        # This is ours!
        if circuit_id in self.circuits:
            circuit = self.circuits[circuit_id]
            self._ours_on_created_extended(circuit, message)
            return True
        return False

    def _ours_on_created_extended(self, circuit, message):
        """
        @param ExtendedMessage | CreatedMessage message: the CREATED or
            EXTENDED message we received
        """

        request = self.dispersy.callback.call(
            self.request_cache.get,
            args=(CircuitRequestCache.create_identifier(circuit.circuit_id),))

        candidate_list = message.candidate_list

        circuit.add_hop(circuit.unverified_hop)
        circuit.unverified_hop = None

        dispersy = self.dispersy
        if dispersy.lan_address in candidate_list:
            del candidate_list[dispersy.lan_address]

        if dispersy.wan_address in candidate_list:
            del candidate_list[dispersy.wan_address]

        for hop in circuit.hops:
            if hop.address in candidate_list:
                del candidate_list[hop.address]

        if circuit.state == CIRCUIT_STATE_EXTENDING:
            try:
                circuit.extend_strategy.extend(candidate_list)
            except ValueError:
                self._logger.exception("Cannot extend due to exception:")
                reason = 'Extend error, state = %s' % circuit.state
                self.remove_circuit(circuit.circuit_id, reason)

        elif circuit.state == CIRCUIT_STATE_READY:
            request.on_success()

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, \
                NTFY_CREATED, NTFY_EXTENDED

            if len(circuit.hops) == 1:
                self.notifier.notify(
                    NTFY_ANONTUNNEL, NTFY_CREATED, circuit)
            else:
                self.notifier.notify(
                    NTFY_ANONTUNNEL, NTFY_EXTENDED, circuit)

    def on_data(self, circuit_id, candidate, message):
        """
        Handles incoming DATA message

        Determines whether the data comes from the outside world (origin set)
        or whether the data came from the origin (destination set)

        If the data comes from the outside world the on_incoming_from_tunnel
        method is called on the observers and the circuit is marked as active

        When the data comes from the origin we need to EXIT to the outside
        world. This is left to the observers as well, by calling the
        on_exiting_from_tunnel method.

        @param int circuit_id: the circuit's id we received the DATA message on
        @param Candidate|None candidate: the messenger of the packet
        @param DataMessage message: the message's content

        @return: whether the message could be handled correctly
        """

        # If its our circuit, the messenger is the candidate assigned to that
        # circuit and the DATA's destination is set to the zero-address then
        # the packet is from the outside world and addressed to us from
        if circuit_id in self.circuits and message.origin \
                and candidate == self.circuits[circuit_id].candidate:
            self._logger.debug("Exit socket at {0}"
                               .format(message.destination))

            self.circuits[circuit_id].beat_heart()
            self.__notify(
                "on_incoming_from_tunnel", self, self.circuits[circuit_id],
                message.origin, message.data)

            return True

        # It is not our circuit so we got it from a relay, we need to EXIT it!
        if message.destination != ('0.0.0.0', 0):
            self.__notify("on_exiting_from_tunnel", circuit_id, candidate,
                          message.destination, message.data)

            return True
        return False

    def on_extend(self, circuit_id, candidate, message):
        """
        Upon reception of a EXTEND message the message is forwarded over the
        Circuit if possible. At the end of the circuit a CREATE request is
        send to the Proxy to extend the circuit with. It's CREATED reply will
        eventually be received and propagated back along the Circuit.

        @param int circuit_id: the circuit's id we got the EXTEND message on
        @param Candidate candidate: the relay which sent us the EXTEND
        @param ExtendMessage message: the message's content

        @return: whether the message could be handled correctly
        """

        if message.extend_with:
            extend_with_addr = message.extend_with
            self._logger.warning(
                "ON_EXTEND send CREATE for circuit (%s, %d) to %s:%d!",
                candidate,
                circuit_id,
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
            assert not current_relay.online, \
                "shouldn't be called whenever relay is online, " \
                "the extend message should have been forwarded"

            # We will just forget the attempt and try again, possible with
            # another candidate
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

        extend_candidate = self._get_cached_candidate(extend_with_addr)
        return self.send_message(extend_candidate, new_circuit_id,
                                 MESSAGE_CREATE, CreateMessage(key))

    def on_extended(self, circuit_id, candidate, message):
        """
        A circuit has been extended, forward the acknowledgment back to the
        origin of the EXTEND. If we are the origin update our records.

        @param int circuit_id: the circuit's id we got the EXTENDED message on
        @param Candidate candidate: the relay which sent us the EXTENDED
        @param ExtendedMessage message: the message's content

        @return: whether the message could be handled correctly
        """

        circuit = self.circuits[circuit_id]
        self._ours_on_created_extended(circuit, message)
        return True

    def create_ping(self, candidate, circuit_id):
        """
        Creates, sends and keeps track of a PING message to given candidate on
        the specified circuit.

        @param Candidate candidate: the candidate to which we want to sent a
            ping
        @param int circuit_id: the circuit id to sent the ping over
        """

        def __do_add():
            identifier = PingRequestCache.create_identifier(circuit_id)
            if not self._request_cache.has(identifier):
                cache = PingRequestCache(self, circuit_id)
                self._request_cache.add(cache)

        self._dispersy.callback.register(__do_add)

        self._logger.debug("SEND PING TO CIRCUIT {0}".format(circuit_id))
        self.send_message(candidate, circuit_id, MESSAGE_PING, PingMessage())

    def on_ping(self, circuit_id, candidate, message):
        """
        Upon reception of a PING message we respond with a PONG message

        @param int circuit_id: the circuit's id we got the PING from
        @param Candidate candidate: the relay we got the PING from
        @param PingMessage message: the message's content

        @return: whether the message could be handled correctly
        """
        self._logger.debug("GOT PING FROM CIRCUIT {0}".format(circuit_id))
        return self.send_message(
            destination=candidate,
            circuit_id=circuit_id,
            message_type=MESSAGE_PONG,
            message=PongMessage())

    def on_pong(self, circuit_id, candidate, message):
        """
        When we receive a PONG message on our circuit we can be sure that the
        circuit is alive and well.

        @param int circuit_id: the circuit's id we got the PONG message on
        @param Candidate candidate: the relay which sent us the PONG
        @param PongMessage message: the message's content

        @return: whether the message could be handled correctly
        """
        self._logger.debug("GOT PONG FROM CIRCUIT {0}".format(circuit_id))
        request = self.dispersy.callback.call(
            self._request_cache.get,
            args=(PingRequestCache.create_identifier(circuit_id),))

        if request:
            request.on_pong(message)
            return True
        return False

    def __on_member_heartbeat(self, message, candidate):
        # got introduction_request or introduction_response from candidate
        # not necessarily a new candidate
        if not isinstance(candidate, WalkCandidate) or \
                isinstance(candidate, BootstrapCandidate):
            return

        candidate._associations.clear()
        candidate.associate(message.authentication.member)
        self._heartbeat_candidates[candidate.sock_addr] = candidate

    def _generate_circuit_id(self, neighbour=None):
        circuit_id = random.randint(1, 255000)

        # prevent collisions
        while circuit_id in self.circuits or \
                (neighbour and (neighbour, circuit_id) in self.relay_from_to):
            circuit_id = random.randint(1, 255000)

        return circuit_id

    def send_message(self, destination, circuit_id, message_type, message):
        """
        Send a message to a specified destination and circuit
        @param Candidate destination: the relay's candidate
        @param int circuit_id: the circuit to sent over
        @param str message_type: the messages type, used to determine how to
         serialize it
        @param BaseMessage message: the messages content in object form
        @return:
        """
        for transformer in self.before_send_transformers[message_type]:
            message = transformer(destination, circuit_id, message)

        content = self.proxy_conversion.encode(message_type, message)

        for transformer in self.send_transformers:
            content = transformer(destination, circuit_id, message_type,
                                  content)

        return self.send_packet(destination, circuit_id, message_type, content)

    def send_packet(self, destination, circuit_id, message_type, packet,
                    relayed=False):
        """
        Sends a packet to a relay over the specified circuit
        @param Candidate destination: the relay's candidate structure
        @param int circuit_id: the circuit to sent over
        @param str message_type: the messages type, for logging purposes
        @param str packet: the messages content in serialised form
        @param bool relayed: whether this is a relay packet or not
        @return: whether the send was successful
        """
        assert isinstance(destination, Candidate), type(destination)
        assert isinstance(packet, str), type(packet)

        packet = self.proxy_conversion.add_circuit(packet, circuit_id)

        str_type = MESSAGE_TYPE_STRING.get(
            message_type, "unknown-type-" + str(ord(message_type)))

        self._logger.debug(
            "SEND %s to %s:%d over circuit %d",
            str_type,
            destination.sock_addr[0], destination.sock_addr[1],
            circuit_id)

        self.__dict_inc(self.dispersy.statistics.outgoing,
                        str_type + ('-relayed' if relayed else ''), 1)

        # we need to make sure that this endpoint is thread safe
        return self.dispersy.endpoint.send(
            candidates=[destination],
            packets=[self.__packet_prefix + packet])

    def __dict_inc(self, statistics_dict, key, inc=1):
        key = u"anontunnel-" + key
        self._dispersy.statistics.dict_inc(statistics_dict, key, inc)

    @property
    def active_circuits(self):
        """
        Dict of active circuits, a circuit is active when its state is
        CIRCUIT_STATE_READY
        @rtype: dict[int, Tribler.community.anontunnel.routing.Circuit]
        """
        return {circuit_id: circuit
                for circuit_id, circuit in self.circuits.items()
                if circuit.state == CIRCUIT_STATE_READY}

    def __ping_circuits(self):
        while True:
            try:
                to_be_removed = [
                    self.remove_relay(relay_key, 'no activity')
                    for relay_key, relay in self.relay_from_to.items()
                    if relay.ping_time_remaining == 0]

                self._logger.info("removed %d relays", len(to_be_removed))
                assert all(to_be_removed)

                to_be_pinged = [
                    circuit for circuit in self.circuits.values()
                    if circuit.ping_time_remaining < PING_INTERVAL
                    and circuit.candidate]

                self._logger.info("pinging %d circuits", len(to_be_pinged))
                for circuit in to_be_pinged:
                    self.create_ping(circuit.candidate, circuit.circuit_id)
            except Exception:
                self._logger.exception("Ping error")

            yield PING_INTERVAL

    def __notify(self, method, *args, **kwargs):
        for observer in self.observers:
            try:
                func = getattr(observer, method)
                func(*args, **kwargs)
            except AttributeError:
                pass

    def tunnel_data_to_end(self, ultimate_destination, payload, circuit):
        """
        Tunnel data to the end and request an EXIT to the outside world

        @param (str, int) ultimate_destination: The destination outside the
            tunnel community
        @param str payload: The raw payload to send to the ultimate destination
        @param Tribler.community.anontunnel.routing.Circuit circuit: The
            circuit id to tunnel data over

        @return: Whether the request has been handled successfully
        """

        with self.lock:
            if circuit.goal_hops == 0:
                self.__notify(
                    "on_exiting_from_tunnel",
                    circuit.circuit_id, None, ultimate_destination, payload)
            else:
                self.send_message(
                    circuit.candidate, circuit.circuit_id, MESSAGE_DATA,
                    DataMessage(ultimate_destination, payload, None))

                self.__notify(
                    "on_send_data",
                    circuit.circuit_id, circuit.candidate,
                    ultimate_destination, payload)

    def tunnel_data_to_origin(self, circuit_id, candidate, source_address,
                              payload):
        """
        Tunnel data to originator

        @param int circuit_id: The circuit's id to return data over
        @param Candidate candidate: The relay to return data over
        @param (str, int) source_address: The source outside the tunnel
            community
        @param str payload: The raw payload to return to the originator

        @return: Whether the request has been handled successfully
        """
        with self.lock:
            result = self.send_message(
                candidate, circuit_id, MESSAGE_DATA,
                DataMessage(None, payload, source_address))

            if result:
                self.__notify("on_enter_tunnel", circuit_id, candidate,
                              source_address, payload)

            return result

    def reserve_circuit(self):
        """
        Reserve a (future) circuit
        @rtype: defer.Deferred
        """

        def __reserve(circuit):
            self._logger.warning("Reserving circuit %d", circuit.circuit_id)
            self._reservations.add(circuit)
            return circuit

        def __errback(error):
            self._logger.error("We got an unhandled error: %s", error)
            return error

        with self.lock:
            free = next((c for c in self.circuits.itervalues()
                         if c not in self._reservations), None)

            if free:
                __reserve(free)
                return free.deferred

            else:
                deferred = defer.Deferred()
                deferred.addErrback(__errback)

                # remove from the list when circuit is ready
                deferred.addCallback(__reserve)
                self._circuit_promises.append(deferred)

                return deferred

    def cancel_reservation(self, circuit):
        """
        Free a circuit from a reservation
        @param Circuit circuit: Circuit to free
        @rtype: bool
        """
        if circuit.circuit_id in self._reservations:
            with self.lock:
                self._reservations.remove(circuit)

                return True
        return False