import logging
import os
import socket
import string
from threading import RLock
from random import getrandbits
import uuid
import sys
import random
import M2Crypto
from Tribler.community.anontunnel.ConnectionHandlers.CircuitReturnHandler import ShortCircuitReturnHandler, CircuitReturnHandler
from Tribler.dispersy.requestcache import NumberCache

from AES import AESdecode
from AES import AESencode

logger = logging.getLogger(__name__)

from Tribler.community.anontunnel.globals import *
from random import randint, randrange
from Tribler.community.anontunnel import ExtendStrategies
from Tribler.community.anontunnel.CircuitLengthStrategies import ConstantCircuitLengthStrategy, RandomCircuitLengthStrategy
from Tribler.community.anontunnel.SelectionStrategies import RandomSelectionStrategy
from traceback import print_exc

from time import time
import hashlib

from Tribler.community.anontunnel.conversion import ProxyConversion, \
    CustomProxyConversion

from Tribler.community.anontunnel.payload import StatsPayload, CreatedMessage, \
    PongMessage, CreateMessage, PingMessage, DataMessage, ExtendedMessage

from Tribler.dispersy.candidate import BootstrapCandidate, WalkCandidate, \
    Candidate
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination
from Tribler.dispersy.distribution import LastSyncDistribution
from Tribler.dispersy.message import Message
from Tribler.dispersy.resolution import PublicResolution


class Hop:
    def __init__(self, address, pub_key, dh_first_part):
        self.address = address
        self.pub_key = pub_key
        self.session_key = None
        self.dh_first_part = dh_first_part

    @property
    def session_key(self):
        return self.session_key
    @property
    def dh_first(self):
        return self.dh_first

    @property
    def host(self):
        return self.address[0]

    @property
    def port(self):
        return self.address[1]

    @staticmethod
    def fromCandidate(candidate):
        hop = Hop(candidate.sock_addr, None, None)
        return hop


ORIGINATOR = "originator"
ENDPOINT = "endpoint"


class ProxySettings:
    def __init__(self):
        length = randint(1, 4)
        length = 2

        self.extend_strategy = ExtendStrategies.NeighbourSubset
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

    def __init__(self, circuit_id, goal_hops=0, candidate=None):
        """
        Instantiate a new Circuit data structure

        :param circuit_id: the id of the candidate circuit
        :param candidate: the first hop of the circuit
        :return: Circuit
        """

        self.circuit_id = circuit_id
        self.candidate = candidate
        self.hops = []
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

        self.unverified_hop = None
        """ :type : Hop """


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

    def __init__(self, dispersy, master_member, raw_server, settings=None, integrate_with_tribler=True):
        Community.__init__(self, dispersy, master_member)

        if not settings:
            settings = ProxySettings()

        self.lock = RLock()

        # Custom conversion
        self.prefix = 'f' * 22 + 'e'  # shouldn't this be "fffffffe".decode("HEX")?
        self.proxy_conversion = CustomProxyConversion()
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
        self.directions = {}
        self.relay_from_to = {}

        self.key = self.my_member.private_key
        self.session_keys = {}

        sr = random.SystemRandom()
        sys.modules["random"] = sr
        self.dh_secret = getrandbits(128)


        # Stats
        self.stats = {
            'bytes_enter': 0,
            'bytes_exit': 0,
            'bytes_returned': 0,
            'dropped_exit': 0,
            'packet_size': 0
        }

        self._record_stats = False
        self.download_stats = None
        self.session_id = uuid.uuid4()
        
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
        dispersy._callback.register(self.calc_speeds)

        if integrate_with_tribler:
            from Tribler.Core.CacheDB.Notifier import Notifier
            self.notifier = Notifier.getInstance()
        else:
            self.notifier = None

    def add_observer(self, observer):
        assert isinstance(observer, TunnelObserver)
        self.__observers.append(observer)

        observer.on_state_change(self, self.online)

    def unload_community(self):
        Community.unload_community(self)

        if self.download_stats:
            self.send_stats()

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

    def calc_speeds(self):
        while True:
            t2 = time()
            for c in self.circuits.values():
                if c.timestamp is None:
                    c.timestamp = time()
                elif c.timestamp < t2:

                    if self.record_stats and (
                            len(c.bytes_up_list) == 0 or c.bytes_up[-1] != c.bytes_up_list[-1] and c.bytes_down[
                        -1] != c.bytes_down_list[-1]):
                        c.bytes_up_list.append(c.bytes_up[-1])
                        c.bytes_down_list.append(c.bytes_down[-1])
                        c.times.append(t2)

                    c.speed_up = 1.0 * (c.bytes_up[1] - c.bytes_up[0]) / (t2 - c.timestamp)
                    c.speed_down = 1.0 * (c.bytes_down[1] - c.bytes_down[0]) / (t2 - c.timestamp)

                    c.timestamp = t2
                    c.bytes_up = [c.bytes_up[1], c.bytes_up[1]]
                    c.bytes_down = [c.bytes_down[1], c.bytes_down[1]]

            for r in self.relay_from_to.values():
                if r.timestamp is None:
                    r.timestamp = time()
                elif r.timestamp < t2:

                    if self.record_stats and (len(r.bytes_list) == 0 or r.bytes[-1] != r.bytes_list[-1]):
                        r.bytes_list.append(r.bytes[-1])
                        r.times.append(t2)

                    r.speed = 1.0 * (r.bytes[1] - r.bytes[0]) / (t2 - r.timestamp)
                    r.timestamp = t2
                    r.bytes = [r.bytes[1], r.bytes[1]]

            yield 1.0

    def _create_stats(self):
        stats = {
            'uuid': str(self.session_id),
            'swift': self.download_stats,
            'bytes_enter': self.stats['bytes_enter'],
            'bytes_exit': self.stats['bytes_exit'],
            'bytes_return': self.stats['bytes_returned'],
            'circuits': [
                {
                    'hops': len(c.hops),
                    'bytes_down': c.bytes_down_list[-1] - c.bytes_down_list[0],
                    'bytes_up': c.bytes_up_list[-1] - c.bytes_up_list[0],
                    'time': c.times[-1] - c.times[0]
                }
                for c in self.get_circuits()
                if len(c.times) >= 2
            ],
            'relays': [
                {
                    'bytes': r.bytes_list[-1],
                    'time': r.times[-1] - r.times[0]
                }
                for r in self.relay_from_to.values()
                if r.times and len(r.times) >= 2
            ]
        }

        return stats

    def __send_stats(self):
        stats = self._create_stats()
        meta = self.get_meta_message(u"stats")
        record = meta.impl(authentication=(self._my_member,),
                           distribution=(self.claim_global_time(),),
                           payload=(stats,))

        logger.warning("Sending stats")
        self.dispersy.store_update_forward([record], True, False, True)

    def send_stats(self):
        self.dispersy.callback.register(self.__send_stats)

    # END OF DISPERSY DEFINED MESSAGES
    # START OF CUSTOM MESSAGES
    def on_bypass_message(self, sock_addr, orig_packet):
        packet = orig_packet[len(self.prefix):]

        dispersy = self._dispersy

        # TODO: we should attempt to get the candidate from the member_heartbeat dict
        # get_candidate has a garbage collector :P
        candidate = self.get_candidate(sock_addr) or Candidate(sock_addr, False)
        circuit_id, data = self.proxy_conversion.get_circuit_and_data(packet)
        relay_key = (candidate, circuit_id)

        # First, relay packet if we know whom to forward message to for this circuit
        if circuit_id > 0 and relay_key in self.relay_from_to:
            next_relay = self.relay_from_to[relay_key]

            if self.directions[circuit_id] == ORIGINATOR:
                # Message is going downstream so I have to add my onion layer
                # logger.debug("Adding AES layer with key %s to circuit %d" % (self.session_keys[next_relay.circuit_id], next_relay.circuit_id))
                data = AESencode(self.session_keys[next_relay.circuit_id], data)

            elif self.directions[circuit_id] == ENDPOINT:
                # Message is going upstream so I have to remove my onion layer
                # logger.debug("Removing AES layer with key %s" % self.session_keys[circuit_id])
                data = AESdecode(self.session_keys[circuit_id], data)

            next_relay.bytes[1] += len(data)

            this_relay_key = (next_relay.candidate, next_relay.circuit_id)
            if this_relay_key in self.relay_from_to:
                this_relay = self.relay_from_to[this_relay_key]
                this_relay.last_incomming = time()
                this_relay.bytes[0] += len(packet)

            packet_type = self.proxy_conversion.get_type(data)
            str_type = MESSAGE_STRING_REPRESENTATION.get(packet_type, 'unknown-type-%d' % ord(packet_type))

            #logger.debug("GOT %s from %s:%d over circuit %d", str_type, candidate.sock_addr[0], candidate.sock_addr[1], circuit_id)

            self.send_packet(next_relay.candidate, next_relay.circuit_id, packet_type, data, relayed=True)
            self.dict_inc(dispersy.statistics.success, str_type + '-relayed')

        # We don't know where to relay this message to, must be for me?
        else:
            try:
                if circuit_id in self.circuits:
                    # I am the originator so I'll peel the onion skins
                    for hop in self.circuits[circuit_id].hops:
                        logger.debug("Removing AES layer for %s:%s with key %s" % (hop.host, hop.port, hop.session_key))
                        data = AESdecode(hop.session_key, data)
            #       if self.circuits[circuit_id].unverified_hop:
            #            logger.debug("Removing AES layer for unverified hop %s:%s with key %s" % (self.circuits[circuit_id].unverified_hop.host, self.circuits[circuit_id].unverified_hop.port, self.circuits[circuit_id].unverified_hop.session_key))
            #           data = AESdecode(self.circuits[circuit_id].unverified_hop.session_key, data)

                elif circuit_id in self.session_keys:
                    # last node in circuit, circuit already exists
                    data = AESdecode(self.session_keys[circuit_id], data)
                else:
                    # last node in circuit, circuit does not exist yet
                    logger.warning("Gotta decrypt with private key, circuit = {}, my circuitkeys so far are {}".format(circuit_id, self.session_keys))
                    data = data

                _, payload = self.proxy_conversion.decode(data)


                packet_type = self.proxy_conversion.get_type(data)
                str_type = MESSAGE_STRING_REPRESENTATION.get(packet_type, 'unknown-type-%d' % ord(packet_type))

                logger.debug("GOT %s from %s:%d over circuit %d", str_type, candidate.sock_addr[0], candidate.sock_addr[1], circuit_id)


                if circuit_id in self.circuits:
                    self.circuits[circuit_id].last_incomming = time()

                if not self.on_custom.get(packet_type, lambda *args:None)(circuit_id, candidate, payload):
                    self.dict_inc(dispersy.statistics.success, str_type + '-ignored')
                    logger.debug("Prev message was IGNORED")
                else:
                    self.dict_inc(dispersy.statistics.success, str_type)
            except Exception as e:
                logger.exception("ERROR from %s:%d over circuit %d", candidate.sock_addr[0], candidate.sock_addr[1], circuit_id)

    class CircuitRequestCache(NumberCache):

        @staticmethod
        def create_number(force_number= -1):
            return force_number if force_number >= 0 else NumberCache.create_number()

        @staticmethod
        def create_identifier(number, force_number= -1):
            assert isinstance(number, (int, long)), type(number)
            return u"request-cache:circuit-request:%d" % (number,)

        def __init__(self, community, force_number):
            NumberCache.__init__(self, community._request_cache, force_number)
            self.community = community

            self.circuit = None
            """ :type : Tribler.community.anontunnel.community.Circuit """

        @property
        def timeout_delay(self):
            return 5.0

        @property
        def cleanup_delay(self):
            return 0.0

        def on_extended(self, extended_message):
            """

            :type extended_message : Tribler.community.anontunnel.payload.ExtendedMessage
            """
            unverified_hop = self.circuit.unverified_hop
            logger.error("Not really verifying hop! Check hashes etc")

            session_key = str(pow(extended_message.key, unverified_hop.dh_first_part, DIFFIE_HELLMAN_MODULUS))
            unverified_hop.session_key = session_key

            self.circuit.hops.append(unverified_hop)
            self.circuit.unverified_hop = None

            candidate_list = extended_message.candidate_list

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
                    logger.error("Cannot extend due to {}".format(e.message))
                    self.community.remove_circuit(self.number, 'extend error on CircuitRequestCache, state = %s' % self.circuit.state)

            elif self.circuit.state == CIRCUIT_STATE_READY:
                self.on_success()

            if self.community.notifier:
                from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_CREATED, NTFY_EXTENDED

                if len(self.circuit.hops) == 1:
                    self.community.notifier.notify(NTFY_ANONTUNNEL, NTFY_CREATED, self.circuit)
                else:
                    self.community.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, self.circuit)

        def on_success(self):
            if self.circuit.state == CIRCUIT_STATE_READY:
                logger.info("Circuit %d is ready", self.number)
                self.community._dispersy._callback.register(self.community._request_cache.pop, args=(self.identifier,))

        def on_timeout(self):
            if not self.circuit.state == CIRCUIT_STATE_READY:
                self.community.remove_circuit(self.number, 'timeout on CircuitRequestCache, state = %s' % self.circuit.state)

    def create_circuit(self, first_hop_candidate, extend_strategy=None):
        try:
            """ Create a new circuit, with one initial hop """

            circuit_id = self._generate_circuit_id(first_hop_candidate)
            cache = self._request_cache.add(ProxyCommunity.CircuitRequestCache(self, circuit_id))

            goal_hops = self.circuit_length_strategy.circuit_length()
            circuit = cache.circuit = Circuit(circuit_id, goal_hops, first_hop_candidate)

            circuit.extend_strategy = extend_strategy(self, circuit) if extend_strategy else self.extend_strategy(self, circuit)
            self.circuits[circuit_id] = circuit

            pub_key = None

            dh_first_part = pow(DIFFIE_HELLMAN_GENERATOR, self.dh_secret, DIFFIE_HELLMAN_MODULUS)
            circuit.unverified_hop = Hop(first_hop_candidate.sock_addr, pub_key, dh_first_part)
            logger.info('Circuit %d is to be created, we want %d hops sending to %s:%d', circuit_id, circuit.goal_hops, first_hop_candidate.sock_addr[0], first_hop_candidate.sock_addr[1])
            self.send_message(first_hop_candidate, circuit_id, MESSAGE_CREATE, CreateMessage(dh_first_part))

            return circuit

        except Exception as e:
            logger.exception("create_circuit")


    def remove_circuit(self, circuit_id, additional_info=''):
        assert isinstance(circuit_id, (long, int)), type(circuit_id)

        if circuit_id in self.circuits:
            logger.info("Breaking circuit %d " + additional_info, circuit_id)

            del self.circuits[circuit_id]

            return True
        return False

    def remove_relay(self, relay_key, additional_info=''):
        if relay_key in self.relay_from_to:
            logger.info(("Breaking relay %s:%d %d " + additional_info) % (relay_key[0].sock_addr[0], relay_key[0].sock_addr[1], relay_key[1]))
            # Only remove one side of the relay, this isn't as pretty but both sides have separate incomming timer, hence
            # after removing one side the other will follow. 
            del self.relay_from_to[relay_key]
            return True
        return False

    def on_create(self, circuit_id, candidate, message):
        """ Handle incoming CREATE message, acknowledge the CREATE request with a CREATED reply """
        logger.info('We joined circuit %d with neighbour %s', circuit_id, candidate)
        logger.info('Received secret %s', message.encrypted_key)

        self.directions[circuit_id] = ORIGINATOR

        key = str(pow(message.encrypted_key, self.dh_secret, DIFFIE_HELLMAN_MODULUS))

        self.session_keys[circuit_id] = key

        return_key = str(pow(DIFFIE_HELLMAN_GENERATOR, self.dh_secret, DIFFIE_HELLMAN_MODULUS))
        cand_dict = {}
        for i in range(1, 5):
            candidate_temp = next(self.dispersy_yield_verified_candidates(), None)
            if not candidate_temp:
                break
            cand_dict[candidate_temp.sock_addr] = "mykey"

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_JOINED
            self.notifier.notify(NTFY_ANONTUNNEL, NTFY_JOINED, candidate.sock_addr, circuit_id)

        return self.send_message(candidate, circuit_id, MESSAGE_CREATED, CreatedMessage(return_key, cand_dict))

    def on_created(self, circuit_id, candidate, message):
        """ Handle incoming CREATED messages relay them backwards towards the originator if necessary """
        relay_key = (circuit_id, candidate)
        if relay_key in self.relay_from_to:
            extended_message = ExtendedMessage(message.key, message.candidate_list)
            forwarding_relay = self.relay_from_to[relay_key]
            return self.send_message(forwarding_relay.candidate, forwarding_relay.circuit_id, MESSAGE_EXTENDED, extended_message)


        self.directions[circuit_id] = ENDPOINT
        request = self._dispersy._callback.call(self._request_cache.get, args=(ProxyCommunity.CircuitRequestCache.create_identifier(circuit_id),))
        if request:
            request.on_extended(message)
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

        encrypted_secret = message.encrypted_secret

        self.directions[new_circuit_id] = ORIGINATOR
        self.directions[circuit_id] = ENDPOINT

        return self.send_message(extend_with, new_circuit_id, MESSAGE_CREATE, CreateMessage(encrypted_secret))

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
            return force_number if force_number >= 0 else NumberCache.create_number()

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


    # got introduction_request or introduction_response from candidate
    # not necessarily a new candidate
    def on_member_heartbeat(self, candidate):
        assert isinstance(candidate, WalkCandidate), type(candidate)
        if not isinstance(candidate, BootstrapCandidate):

            if len(self.circuits) < MAX_CIRCUITS_TO_CREATE and candidate not in self.circuits.values():
                self.create_circuit(candidate)

    def _generate_circuit_id(self, neighbour):
        # TODO: why is the circuit_id so small? The conversion is using a unsigned long.
        circuit_id = randint(1, 255000)

        # prevent collisions
        while circuit_id in self.circuits or (neighbour, circuit_id) in self.relay_from_to:
            circuit_id = randint(1, 255000)

        return circuit_id

    def send_message(self, destination, circuit_id, message_type, message):
        content = self.proxy_conversion.encode(message_type, message)
        if circuit_id in self.circuits:
            # I am the originator so I have to create the full onion
            circuit = self.circuits[circuit_id]
            hops = circuit.hops

            for hop in reversed(hops):
                logger.debug("Adding AES layer for hop %s:%s with key %s" % (hop.host, hop.port, hop.session_key))
                content = AESencode(hop.session_key, content)
        elif circuit_id in self.session_keys:
           if message_type == MESSAGE_CREATED:
                logger.debug("Adding public key encryption for circuit %s" % (circuit_id))
                logger.error("Still have to implement public key encryption for CREATED message")
           else:
                content = AESencode(self.session_keys[circuit_id], content)
                logger.debug("Adding AES layer for circuit %s with key %s" % (circuit_id, self.session_keys[circuit_id]))
          #packet = self.proxy_conversion.add_circuit(content, circuit_id)

        return self.send_packet(destination, circuit_id, message_type, content)


    def send_packet(self, destination, circuit_id, message_type, packet, relayed=False):
        assert isinstance(destination, Candidate), type(destination)
        assert isinstance(packet, str), type(packet)
        # assert packet.startswith(self.prefix)

        packet = self.proxy_conversion.add_circuit(packet, circuit_id)

        str_type = MESSAGE_STRING_REPRESENTATION.get(message_type, "unknown-type-"+str(ord(message_type)))

        logger.debug("SEND %s to %s:%d over circuit %d", str_type, destination.sock_addr[0], destination.sock_addr[1], circuit_id)

        self.dict_inc(self.dispersy.statistics.outgoing, str_type + ('-relayed' if relayed else ''), 1)

        # we need to make sure that this endpoint is threadsafe
        return self.dispersy.endpoint.send([destination], [self.prefix + packet])

    def dict_inc(self, statistics_dict, key, inc=1):
        pass
        #self.dispersy._callback.register(self._dispersy.statistics.dict_inc, args=(statistics_dict, u"anontunnel-" + key, inc))

    # CIRCUIT STUFFS
    def get_circuits(self):
        return self.circuits.values()

    @property
    def active_circuits(self):
        # Circuit is active when it has received a CREATED for it and the final length and the length is 0
        return [circuit for circuit in self.circuits.values() if circuit.state == CIRCUIT_STATE_READY]

    def check_ready(self):
        while True:
            self.online = self.circuit_selection_strategy.can_select(self.active_circuits)
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

                if not ultimate_destination:
                    ultimate_destination = ("0.0.0.0", 0)

                logger.debug("Sending data with origin %s to %s over circuit %d with ultimate destination %s:%d",
                            origin, address, circuit_id, *ultimate_destination)
            except Exception, e:
                logger.exception(e)
