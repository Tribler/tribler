"""
AnonTunnel community module
"""

# Python imports
import logging
import random
import threading
import time
from collections import defaultdict

from twisted.internet.task import LoopingCall
from twisted.internet import reactor

from Tribler.community.anontunnel import crypto, extendstrategies, selectionstrategies, lengthstrategies
from Tribler.community.anontunnel.cache import CircuitRequestCache, PingRequestCache, CreatedRequestCache
from Tribler.community.anontunnel.conversion import CustomProxyConversion, ProxyConversion
from Tribler.community.anontunnel.globals import (MESSAGE_EXTEND, MESSAGE_CREATE, MESSAGE_CREATED, MESSAGE_DATA,
                                                  MESSAGE_EXTENDED, MESSAGE_PING, MESSAGE_PONG, MESSAGE_TYPE_STRING,
                                                  CIRCUIT_STATE_READY, CIRCUIT_STATE_EXTENDING, ORIGINATOR,
                                                  PING_INTERVAL, ENDPOINT)
from Tribler.community.anontunnel.payload import (StatsPayload, CreateMessage, CreatedMessage, ExtendedMessage,
                                                  PongMessage, PingMessage, DataMessage)
from Tribler.community.anontunnel.routing import Circuit, Hop, RelayRoute
from Tribler.community.anontunnel.tests.test_libtorrent import LibtorrentTest
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.dispersy.candidate import Candidate, WalkCandidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.util import blocking_call_on_reactor_thread, call_on_reactor_thread


__author__ = 'chris'



class ProxySettings:
    """
    Data structure containing settings, including some defaults,
    for the ProxyCommunity
    """

    def __init__(self):
        length = random.randint(3, 3)

        self.max_circuits = 1
        self.delay = 300

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
    @type tribler_session: Tribler.Core.Session.Session
    """

    def __init__(self, dispersy, master_member, my_member):
        super(ProxyCommunity, self).__init__(dispersy, master_member, my_member)

        self.lock = threading.RLock()
        self._logger = logging.getLogger(__name__)

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

        # Map destination address to the circuit to be used
        self.destination_circuit = {}
        ''' @type: dict[(str, int), int] '''

        self.circuit_pools = []
        ''' :type : list[CircuitPool] '''

    def initialize(self, tribler_session=None, settings=None):
        super(ProxyCommunity, self).initialize()

        self.settings = settings if settings else ProxySettings()
        self._tribler_session = tribler_session

        # Attach message handlers
        self._initiate_message_handlers()

        # add self to crypto
        self.settings.crypto.set_proxy(self)

        # Enable global counters
        from Tribler.community.anontunnel.stats import StatsCollector

        self.global_stats = StatsCollector(self, "global")
        self.global_stats.start()

        # Listen to prefix endpoint
        try:
            self._dispersy.endpoint.listen_to(self.__packet_prefix, self.__handle_packet)
        except AttributeError:
            self._logger.error("Cannot listen to our prefix, are you sure that you are using the DispersyBypassEndpoint?")

        if self._tribler_session:
            from Tribler.Core.CacheDB.Notifier import Notifier
            self.notifier = Notifier.getInstance()
            delay = self.settings.delay if self.settings.delay is not None else 300
            self._tribler_session.lm.rawserver.add_task(lambda: LibtorrentTest(self, self._tribler_session, delay))
        else:
            self.notifier = None

        self._pending_tasks["discover"] = lc = LoopingCall(self.__discover)
        lc.start(5, now=True)

        self._pending_tasks["ping circuits"] = lc = LoopingCall(self.__ping_circuits)
        lc.start(PING_INTERVAL)


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

        master = dispersy.get_member(public_key=master_key)
        return [master]

    @property
    def crypto(self):
        """
        @rtype: ElgamalCrypto
        """
        return self.dispersy.crypto

    @property
    def packet_crypto(self):
        return self.settings.crypto

    def __discover(self):
        circuits_needed = lambda: max(
            sum(pool.lacking for pool in self.circuit_pools),
            self.settings.max_circuits - len(self.circuits)
        )

        with self.lock:
            for i in range(0, circuits_needed()):
                self._logger.debug("Need %d new circuits!", circuits_needed())
                goal_hops = self.settings.length_strategy.circuit_length()

                if goal_hops == 0:
                    circuit_id = self._generate_circuit_id()
                    self.circuits[circuit_id] = Circuit(circuit_id, self)

                    first_pool = next((pool for pool in self.circuit_pools if pool.lacking), None)
                    if first_pool:
                        first_pool.fill(self.circuits[circuit_id])

                else:
                    circuit_candidates = set([c.first_hop for c in self.circuits.values()])
                    candidate = next(
                        (
                            c for c in self.dispersy_yield_verified_candidates()
                            if (c.sock_addr not in circuit_candidates) and \
                               self.packet_crypto.is_key_compatible(c.get_member()._ec)
                        ), None
                    )

                    if candidate is None:
                        return
                    else:
                        try:
                            self.create_circuit(candidate, goal_hops)
                        except:
                            self._logger.exception("Error creating circuit while running __discover")

    def unload_community(self):
        """
        Called by dispersy when the ProxyCommunity is being unloaded
        @return:
        """
        for observer in self.observers:
            observer.on_unload()
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
        return super(ProxyCommunity, self).initiate_meta_messages() + [
            Message(
                self,
                u"stats",
                MemberAuthentication(),
                PublicResolution(),
                LastSyncDistribution(synchronization_direction=u"DESC",
                                     priority=128, history_size=1),
                CommunityDestination(node_count=10),
                StatsPayload(),
                self._generic_timeline_check,
                self._on_stats
        )]

    def _generic_timeline_check(self, messages):
        meta = messages[0].meta
        if isinstance(meta.authentication, NoAuthentication):
            # we can not timeline.check this message because it uses the NoAuthentication policy
            for message in messages:
                yield message

        else:
            for message in messages:
                allowed, proofs = self.timeline.check(message)
                if allowed:
                    yield message
                else:
                    yield DelayMessageByProof(message)

    def _on_stats(self, messages):
        for observer in self.observers:
            for message in messages:
                observer.on_tunnel_stats(self, message.authentication.member, message.candidate, message.payload.stats)

    @call_on_reactor_thread
    def send_stats(self, stats):
        """
        Send a stats message to the community
        @param dict stats: the statistics dictionary to share
        """

        meta = self.get_meta_message(u"stats")
        record = meta.impl(authentication=(self._my_member,),
                           distribution=(self.claim_global_time(),),
                           payload=(stats,))

        self._logger.warning("Sending stats")
        self.dispersy.store_update_forward([record], True, False, True)

    def __handle_incoming(self, circuit_id, am_originator, sock_addr, data):
        # Let packet_crypto handle decrypting the incoming packet
        data = self.packet_crypto.handle_incoming_packet(sock_addr, circuit_id, data)

        if not data:
            self._logger.error("Circuit ID {0} doesn't talk crypto language, dropping packet".format(circuit_id))
            return False

        # Try to parse the packet

        try:
            _, payload = self.proxy_conversion.decode(data)
        except KeyError as e:
            self._logger.warning("Cannot decode payload, probably orphaned session")
            return False;

        packet_type = self.proxy_conversion.get_type(data)
        str_type = MESSAGE_TYPE_STRING.get(packet_type)

        # Let packet_crypto handle decrypting packet contents
        payload = self.packet_crypto.handle_incoming_packet_content(sock_addr, circuit_id, payload, packet_type)

        # If un-decrypt-able, drop packet
        if not payload:
            self._logger.warning("IGNORED %s from %s:%d over circuit %d",
                                 str_type, sock_addr[0],
                                 sock_addr[1], circuit_id)
            return False

        if am_originator:
            self.circuits[circuit_id].beat_heart()

        handler = self._message_handlers[packet_type]
        result = handler(circuit_id, sock_addr, payload)

        if result:
            self.__dict_inc(u"success", str_type)
        else:
            self.__dict_inc(u"success", str_type + '-ignored')
            self._logger.debug("Prev message was IGNORED")

        return True

    def __relay(self, circuit_id, data, relay_key, sock_addr):
        # First, relay packet if we know whom to forward message to for
        # this circuit. This happens only when the circuit is already
        # established with both parent and child and if the node is not
        # waiting for a CREATED message from the child

        direction = self.directions[relay_key]
        next_relay = self.relay_from_to[relay_key]

        # let packet_crypto handle en-/decrypting relay packet
        data = self.packet_crypto.handle_relay_packet(direction, sock_addr, circuit_id, data)

        if not data:
            return False

        this_relay_key = (next_relay.sock_addr, next_relay.circuit_id)

        if this_relay_key in self.relay_from_to:
            this_relay = self.relay_from_to[this_relay_key]
            this_relay.last_incoming = time.time()

            # TODO: check whether direction is set correctly here!
            for observer in self.observers:
                observer.on_relay(this_relay_key, relay_key, direction, data)

        packet_type = self.proxy_conversion.get_type(data)

        str_type = MESSAGE_TYPE_STRING.get(
            packet_type, 'unknown-type-%d' % ord(packet_type)
        )

        self.send_packet(
            destination=next_relay.sock_addr,
            circuit_id=next_relay.circuit_id,
            message_type=packet_type,
            packet=data,
            relayed=True
        )

        self.__dict_inc(u"success", str_type + '-relayed')

        return True

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
                result = self.__relay(circuit_id, data, relay_key, sock_addr)
            else:
                result = self.__handle_incoming(circuit_id, is_originator, sock_addr, data)
        except:
            result = False
            self._logger.exception(
                "Incoming from %s on %d message error."
                "INITIAL=%s, ORIGINATOR=%s, RELAY=%s",
                sock_addr, circuit_id, is_initial, is_originator, is_relay)

        if not result:
            if is_relay:
                self.remove_relay(relay_key, "error on incoming packet!")
            elif is_originator:
                self.remove_circuit(circuit_id, "error on incoming packet!")

    def create_circuit(self, first_hop, goal_hops, extend_strategy=None, deferred=None):
        """ Create a new circuit, with one initial hop

        @param WalkCandidate first_hop: The first hop of our circuit, needs to
            be a candidate.
        @param int goal_hops: The number of hops the circuit should reach
        @param T <= extendstrategies.ExtendStrategy extend_strategy:
        The extend strategy used

        @rtype: Tribler.community.anontunnel.routing.Circuit
        """

        if not (goal_hops > 0):
            raise ValueError("We can only create circuits with more than 0 hops using create_circuit()!")

        # TODO(emilon): Can this lock be removed or at least be converted to a DeferredLock?
        with self.lock:
            circuit_id = self._generate_circuit_id(first_hop.sock_addr)
            circuit = Circuit(
                circuit_id=circuit_id,
                goal_hops=goal_hops,
                first_hop=first_hop.sock_addr,
                proxy=self)

            @blocking_call_on_reactor_thread
            def _add_cache():
                self._request_cache.add(CircuitRequestCache(self, circuit))

            _add_cache()

            if extend_strategy:
                circuit.extend_strategy = extend_strategy
            else:
                circuit.extend_strategy = self.settings.extend_strategy(
                    self, circuit)

            hop_public_key = first_hop.get_member()._ec
            circuit.unverified_hop = Hop(hop_public_key)
            circuit.unverified_hop.address = first_hop.sock_addr

            self._logger.warning("Creating circuit %d of %d hops. Fist hop: %s:%d",
                circuit_id, circuit.goal_hops,
                first_hop.sock_addr[0],
                first_hop.sock_addr[1]
            )

            self.circuits[circuit_id] = circuit
            self.waiting_for[(first_hop.sock_addr, circuit_id)] = True

            destination_key = first_hop.get_member()._ec
            self.send_message(first_hop.sock_addr, circuit_id, MESSAGE_CREATE,
                              CreateMessage("", self.my_member.public_key, destination_key))

            return circuit

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
            for observer in self.observers:
                observer.on_break_circuit(circuit)

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

            for observer in self.observers:
                observer.on_break_relay(relay_key)

            return True
        return False

    def on_create(self, circuit_id, sock_addr, message):
        """
        Handle incoming CREATE message, acknowledge the CREATE request with a
        CREATED reply

        @param int circuit_id: The circuit's identifier
        @param (string, int) sock_addr: The candidate we got a CREATE message from
        @param CreateMessage message: The message's payload
        """
        relay_key = (sock_addr, circuit_id)
        self.directions[relay_key] = ENDPOINT
        self._logger.info('We joined circuit %d with neighbour %s'
                          , circuit_id, sock_addr)

        candidates = {}
        ''' :type : dict[str, WalkCandidate] '''

        for _ in range(1, 5):
            candidate_temp = next((c for c in self.dispersy_yield_verified_candidates() if self.packet_crypto.is_candidate_compatible(c)), None)
            " :type: WalkCandidate"

            if not candidate_temp:
                break

            candidates[candidate_temp.get_member().public_key] = candidate_temp

        candidate_list = [c.get_member().public_key for c in candidates.itervalues()]

        self.create_created_cache(circuit_id, sock_addr, candidates)

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_JOINED

            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_JOINED,
                                 sock_addr, circuit_id)

        return self.send_message(
            destination=sock_addr,
            circuit_id=circuit_id,
            message_type=MESSAGE_CREATED,
            message=CreatedMessage(candidate_list, reply_to=message)
        )

    def on_created(self, circuit_id, sock_addr, message):
        """ Handle incoming CREATED messages relay them backwards towards
        the originator if necessary

        @param int circuit_id: The circuit's id we got a CREATED message on
        @param (string, int) sock_addr: The candidate we got the message from
        @param CreatedMessage message: The message we received

        @return: whether the message could be handled correctly

        """
        relay_key = (sock_addr, circuit_id)

        if not relay_key in self.waiting_for:
            self._logger.error("Got an unexpected CREATED message for circuit %d from %s:%d", circuit_id, *sock_addr)
            return False

        del self.waiting_for[relay_key]
        self.directions[relay_key] = ORIGINATOR
        if relay_key in self.relay_from_to:
            self._logger.debug("Got CREATED message, "
                               "forward as EXTENDED to origin.")
            extended_message = ExtendedMessage(message.key,
                                               message.candidate_list)
            forwarding_relay = self.relay_from_to[relay_key]

            return self.send_message(forwarding_relay.sock_addr, forwarding_relay.circuit_id,
                                     MESSAGE_EXTENDED, extended_message)

        # This is ours!
        if circuit_id in self.circuits:
            circuit = self.circuits[circuit_id]
            return self._ours_on_created_extended(circuit, message)

        return False

    def _ours_on_created_extended(self, circuit, message):
        """
        @param ExtendedMessage | CreatedMessage message: the CREATED or
            EXTENDED message we received
        """

        @blocking_call_on_reactor_thread
        def _get_cache():
            return self.request_cache.get(CircuitRequestCache.PREFIX, CircuitRequestCache.create_identifier(circuit))

        request = _get_cache()
        candidate_list = message.candidate_list

        circuit.add_hop(circuit.unverified_hop)
        circuit.unverified_hop = None

        if self.my_member.public_key in candidate_list:
            candidate_list.remove(self.my_member.public_key)

        for hop in circuit.hops:
            if hop.public_key in candidate_list:
                candidate_list.remove(hop.public_key)

        for i in range(len(candidate_list) - 1, -1, -1):
            public_key = self.crypto.key_from_public_bin(candidate_list[i])
            if not self.packet_crypto.is_key_compatible(public_key):
                candidate_list.pop(i)

        if circuit.state == CIRCUIT_STATE_EXTENDING:
            try:
                if not circuit.extend_strategy.extend(candidate_list):
                    raise ValueError("Extend strategy returned False")
            except BaseException as e:
                self.remove_circuit(circuit.circuit_id, e.message)
                return False

        elif circuit.state == CIRCUIT_STATE_READY:
            reactor.callFromThread(request.on_success)

            first_pool = next((pool for pool in self.circuit_pools if pool.lacking), None)
            if first_pool:
                first_pool.fill(circuit)
        else:
            return False

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, \
                NTFY_CREATED, NTFY_EXTENDED

            if len(circuit.hops) == 1:
                self.notifier.notify(
                    NTFY_ANONTUNNEL, NTFY_CREATED, circuit)
            else:
                self.notifier.notify(
                    NTFY_ANONTUNNEL, NTFY_EXTENDED, circuit)

        return True

    def on_data(self, circuit_id, sock_addr, message):
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
        @param (string, int) sock_addr: the messenger of the packet
        @param DataMessage message: the message's content

        @return: whether the message could be handled correctly
        """

        # If its our circuit, the messenger is the candidate assigned to that
        # circuit and the DATA's destination is set to the zero-address then
        # the packet is from the outside world and addressed to us from
        if circuit_id in self.circuits and message.origin \
                and sock_addr == self.circuits[circuit_id].first_hop:

            self.circuits[circuit_id].beat_heart()
            for observer in self.observers:
                observer.on_incoming_from_tunnel(self, self.circuits[circuit_id], message.origin, message.data)

            return True
        # It is not our circuit so we got it from a relay, we need to EXIT it!
        if message.destination != ('0.0.0.0', 0):

            for observer in self.observers:
                observer.on_exiting_from_tunnel(circuit_id, sock_addr, message.destination, message.data)

            return True
        return False

    def on_extend(self, circuit_id, sock_addr, message):
        """
        Upon reception of a EXTEND message the message is forwarded over the
        Circuit if possible. At the end of the circuit a CREATE request is
        send to the Proxy to extend the circuit with. It's CREATED reply will
        eventually be received and propagated back along the Circuit.

        @param int circuit_id: the circuit's id we got the EXTEND message on
        @param (string, int) sock_addr: the relay which sent us the EXTEND
        @param ExtendMessage message: the message's content

        @return: whether the message could be handled correctly
        """

        if message.extend_with:
            cache = self.pop_created_cache(circuit_id, sock_addr)

            if not cache:
                self._logger.warning("Cannot find created cache for circuit %d", circuit_id)
                return False

            extend_candidate = cache.candidates[message.extend_with]

            self._logger.warning(
                "ON_EXTEND send CREATE for circuit (%s, %d) to %s:%d!",
                sock_addr,
                circuit_id,
                extend_candidate.sock_addr[0],
                extend_candidate.sock_addr[1])
        else:
            self._logger.error("Cancelling EXTEND, no candidate!")
            return

        relay_key = (sock_addr, circuit_id)
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

        new_circuit_id = self._generate_circuit_id(extend_candidate.sock_addr)
        to_key = (extend_candidate.sock_addr, new_circuit_id)

        self.waiting_for[to_key] = True
        self.relay_from_to[to_key] = RelayRoute(circuit_id, sock_addr)
        self.relay_from_to[relay_key] = RelayRoute(new_circuit_id,
                                                   extend_candidate.sock_addr)

        key = message.key

        self.directions[to_key] = ORIGINATOR
        self.directions[relay_key] = ENDPOINT

        self._logger.info("Extending circuit, got candidate with IP %s:%d from cache", *extend_candidate.sock_addr)
        destination_key = extend_candidate.get_member()._ec
        return self.send_message(extend_candidate.sock_addr, new_circuit_id,
                                 MESSAGE_CREATE, CreateMessage(key, self.my_member.public_key, destination_key))

    def on_extended(self, circuit_id, candidate, message):
        """
        A circuit has been extended, forward the acknowledgment back to the
        origin of the EXTEND. If we are the origin update our records.

        @param int circuit_id: the circuit's id we got the EXTENDED message on
        @param (string, int) sock_addr: the relay which sent us the EXTENDED
        @param ExtendedMessage message: the message's content

        @return: whether the message could be handled correctly
        """

        circuit = self.circuits[circuit_id]
        return self._ours_on_created_extended(circuit, message)

    def create_ping(self, sock_addr, circuit):
        """
        Creates, sends and keeps track of a PING message to given candidate on
        the specified circuit.

        @param (string, int) sock_addr: the candidate to which we want to sent a
            ping
        @param Circuit circuit: the circuit id to sent the ping over
        """
        circuit_id = circuit.circuit_id
        @call_on_reactor_thread
        def _create_ping():
            if not self._request_cache.has(PingRequestCache.PREFIX, circuit_id):
                cache = PingRequestCache(self, circuit)
                self._request_cache.add(cache)

        _create_ping()
        self._logger.debug("SEND PING TO CIRCUIT {0}".format(circuit_id))

        self.send_message(sock_addr, circuit_id, MESSAGE_PING, PingMessage())

    def on_ping(self, circuit_id, sock_addr, message):
        """
        Upon reception of a PING message we respond with a PONG message

        @param int circuit_id: the circuit's id we got the PING from
        @param (string, int) sock_addr: the relay we got the PING from
        @param PingMessage message: the message's content

        @return: whether the message could be handled correctly
        """
        self._logger.debug("GOT PING FROM CIRCUIT {0}".format(circuit_id))
        return self.send_message(
            destination=sock_addr,
            circuit_id=circuit_id,
            message_type=MESSAGE_PONG,
            message=PongMessage())

    def on_pong(self, circuit_id, sock_addr, message):
        """
        When we receive a PONG message on our circuit we can be sure that the
        circuit is alive and well.

        @param int circuit_id: the circuit's id we got the PONG message on
        @param (string, int) sock_addr: the relay which sent us the PONG
        @param PongMessage message: the message's content

        @return: whether the message could be handled correctly
        """

        @blocking_call_on_reactor_thread
        def pop_cache():
            return self._request_cache.pop(PingRequestCache.PREFIX, circuit_id)

        request = pop_cache()

        if request:
            request.on_pong(message)
            return True
        return False

    def _generate_circuit_id(self, neighbour=None):
        circuit_id = random.getrandbits(32)

        # prevent collisions
        while circuit_id in self.circuits or \
                (neighbour and (neighbour, circuit_id) in self.relay_from_to):
            circuit_id = random.getrandbits(32)

        return circuit_id

    def send_message(self, destination, circuit_id, message_type, message):
        """
        Send a message to a specified destination and circuit
        @param (string, int) destination: the relay's candidate
        @param int circuit_id: the circuit to sent over
        @param str message_type: the messages type, used to determine how to
         serialize it
        @param BaseMessage message: the messages content in object form
        @return:
        """
        message = self.packet_crypto.handle_outgoing_packet_content(destination, circuit_id, message, message_type)

        if message is None:
            return False

        content = self.proxy_conversion.encode(message_type, message)
        content = self.packet_crypto.handle_outgoing_packet(destination, circuit_id, message_type, message, content)

        if content is None:
            return False

        return self.send_packet(destination, circuit_id, message_type, content)

    def send_packet(self, destination, circuit_id, message_type, packet,
                    relayed=False):
        """
        Sends a packet to a relay over the specified circuit
        @param (string, int): the relay's candidate structure
        @param int circuit_id: the circuit to sent over
        @param str message_type: the messages type, for logging purposes
        @param str packet: the messages content in serialised form
        @param bool relayed: whether this is a relay packet or not
        @return: whether the send was successful
        """
        assert isinstance(packet, str), type(packet)

        packet = self.proxy_conversion.add_circuit(packet, circuit_id)

        str_type = MESSAGE_TYPE_STRING.get(
            message_type, "unknown-type-" + str(ord(message_type)))

        # we need to make sure that this endpoint is thread safe
        return self.dispersy._send_packets([Candidate(destination, False)], [self.__packet_prefix + packet],
            self, '-caused by %s-' % (str_type + ('-relayed' if relayed else '')))

    def __dict_inc(self, statistics_dict, key, inc=1):
        key = u"anontunnel-" + key
        self.statistics.increase_msg_count(statistics_dict, key, inc)

    @property
    def active_circuits(self):
        """
        Dict of active circuits, a circuit is active when its state is
        CIRCUIT_STATE_READY
        @rtype: dict[int, Tribler.community.anontunnel.routing.Circuit]
        """
        return dict((circuit_id, circuit)
                for circuit_id, circuit in self.circuits.items()
                if circuit.state == CIRCUIT_STATE_READY)

    def __ping_circuits(self):
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
                and circuit.first_hop]

            # self._logger.info("pinging %d circuits", len(to_be_pinged))
            for circuit in to_be_pinged:
                self.create_ping(circuit.first_hop, circuit)
        except Exception:
            self._logger.error("Ping error")
            raise

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

        if circuit.goal_hops == 0:
            for observer in self.observers:
                observer.on_exiting_from_tunnel(circuit.circuit_id, None, ultimate_destination, payload)
        else:
            self.send_message(
                circuit.first_hop, circuit.circuit_id, MESSAGE_DATA,
                DataMessage(ultimate_destination, payload, None))

            for observer in self.observers:
                observer.on_send_data(circuit.circuit_id, circuit.first_hop, ultimate_destination, payload)

    def tunnel_data_to_origin(self, circuit_id, sock_addr, source_address,
                              payload):
        """
        Tunnel data to originator

        @param int circuit_id: The circuit's id to return data over
        @param Candidate sock_addr: The relay to return data over
        @param (str, int) source_address: The source outside the tunnel
            community
        @param str payload: The raw payload to return to the originator

        @return: Whether the request has been handled successfully
        """
        with self.lock:
            result = self.send_message(
                sock_addr, circuit_id, MESSAGE_DATA,
                DataMessage(None, payload, source_address))

            if result:
                for observer in self.observers:
                    observer.on_enter_tunnel(circuit_id, sock_addr, source_address, payload)

            return result

    @blocking_call_on_reactor_thread
    def create_created_cache(self, circuit_id, candidate, candidates):
        """

        @param int circuit_id: the circuit id we received the CREATE from
        @param WalkCandidate candidate: the candidate we got the CREATE from
        @param dict[str, WalkCandidate] candidates: list of extend candidates we sent back
        """
        self._request_cache.add(CreatedRequestCache(self, circuit_id, candidate, candidates))

    @blocking_call_on_reactor_thread
    def pop_created_cache(self, circuit_id, candidate):
        return self.request_cache.pop(CreatedRequestCache.PREFIX, CreatedRequestCache.create_identifier(circuit_id,
                                                                                                        candidate))
