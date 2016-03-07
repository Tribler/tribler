# Written by Egbert Bouman

import random
import socket
import time
from collections import defaultdict
from cryptography.exceptions import InvalidTag

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.task import LoopingCall

from Tribler import dispersy
from Tribler.Core.Utilities.encoding import decode, encode
from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics
from Tribler.community.tunnel import (CIRCUIT_ID_PORT, CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_READY, CIRCUIT_TYPE_DATA,
                                      CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP, EXIT_NODE, EXIT_NODE_SALT, ORIGINATOR,
                                      ORIGINATOR_SALT, PING_INTERVAL)
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.community.tunnel.conversion import TunnelConversion
from Tribler.community.tunnel.crypto.tunnelcrypto import CryptoException, TunnelCrypto
from Tribler.community.tunnel.payload import (CellPayload, CreatePayload, CreatedPayload, DestroyPayload, ExtendPayload,
                                              ExtendedPayload, PingPayload, PongPayload, StatsRequestPayload,
                                              StatsResponsePayload, TunnelIntroductionRequestPayload,
                                              TunnelIntroductionResponsePayload)
from Tribler.community.tunnel.routing import Circuit, Hop, RelayRoute
from Tribler.dispersy.authentication import MemberAuthentication, NoAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.endpoint import TUNNEL_PREFIX_LENGHT
from Tribler.dispersy.message import DropMessage, Message
from Tribler.dispersy.requestcache import NumberCache, RandomNumberCache
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.util import call_on_reactor_thread
import logging

class CircuitRequestCache(NumberCache):

    def __init__(self, community, circuit):
        super(CircuitRequestCache, self).__init__(community.request_cache, u"anon-circuit", circuit.circuit_id)
        self.tunnel_logger = logging.getLogger('TunnelLogger')
        self.community = community
        self.circuit = circuit
        self.should_forward = False

    def on_timeout(self):
        if self.circuit.state != CIRCUIT_STATE_READY:
            reason = 'timeout on CircuitRequestCache, state = %s, candidate = %s' % (
                self.circuit.state, self.circuit.first_hop)
            self.community.remove_circuit(self.number, reason)

class ExtendRequestCache(NumberCache):
    def __init__(self, community, to_circuit_id, from_circuit_id, candidate_sock_addr, candidate_mid, to_candidate_sock_addr, to_candidate_mid):
        super(ExtendRequestCache, self).__init__(community.request_cache, u"anon-circuit", to_circuit_id)
        self.to_circuit_id = to_circuit_id
        self.from_circuit_id = from_circuit_id
        self.candidate_sock_addr = candidate_sock_addr
        self.candidate_mid = candidate_mid
        self.to_candidate_sock_addr = to_candidate_sock_addr
        self.to_candidate_mid = to_candidate_mid
        self.should_forward = True

    def on_timeout(self):
        pass

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
        super(PingRequestCache, self).__init__(community.request_cache, u"ping")
        self.tunnel_logger = logging.getLogger('TunnelLogger')
        self.circuit = circuit
        self.community = community

    @property
    def timeout_delay(self):
        return PING_INTERVAL + 5

    def on_timeout(self):
        if self.circuit.last_incoming < time.time() - self.timeout_delay:
            self.tunnel_logger.info("PingRequestCache: no response on ping, circuit %d timed out",
                                    self.circuit.circuit_id)
            self.community.remove_circuit(self.circuit.circuit_id, 'ping timeout')


class StatsRequestCache(RandomNumberCache):

    def __init__(self, community, handler):
        super(StatsRequestCache, self).__init__(community.request_cache, u"stats")
        self.handler = handler
        self.community = community

    def on_timeout(self):
        pass


class TunnelExitSocket(DatagramProtocol):

    def __init__(self, circuit_id, community, sock_addr, mid=None):
        self.tunnel_logger = logging.getLogger('TunnelLogger')

        self.port = None
        self.sock_addr = sock_addr
        self.circuit_id = circuit_id
        self.community = community
        self.ips = defaultdict(int)
        self.bytes_up = self.bytes_down = 0
        self.creation_time = time.time()
        self.mid = mid

    def enable(self):
        if not self.enabled:
            self.port = reactor.listenUDP(0, self)

    @property
    def enabled(self):
        return self.port is not None

    def sendto(self, data, destination):
        if self.check_num_packets(destination, False):
            if TunnelConversion.is_allowed(data):
                if dispersy.util.is_valid_address(destination):
                    ip_address = destination[0]
                else:
                    try:
                        ip_address = socket.gethostbyname(destination[0])
                        self.tunnel_logger.info("Resolved ip address %s for hostname %s",
                                                 ip_address,
                                                 destination[0])
                    except:
                        self.tunnel_logger.error("Can't resolve ip address for hostname %s", destination[0])

                try:
                    self.transport.write(data, (ip_address, destination[1]))
                except Exception, e:
                    self.tunnel_logger.error("Failed to write data to transport: %s. Destination: %s",
                                             e[1],
                                             repr(destination))
                    raise

                self.community.increase_bytes_sent(self, len(data))
            else:
                self.tunnel_logger.error("dropping forbidden packets from exit socket with circuit_id %d",
                                         self.circuit_id)

    def datagramReceived(self, data, source):
        self.community.increase_bytes_received(self, len(data))
        if self.check_num_packets(source, True):
            if TunnelConversion.is_allowed(data):
                self.tunnel_data(source, data)
            else:
                self.tunnel_logger.warning("dropping forbidden packets to exit socket with circuit_id %d",
                                           self.circuit_id)

    def tunnel_data(self, source, data):
        self.tunnel_logger.debug("Tunnel data to origin %s for circuit %s", ('0.0.0.0', 0), self.circuit_id)
        self.community.send_data([Candidate(self.sock_addr, False)], self.circuit_id, ('0.0.0.0', 0), source, data)

    def close(self):
        if self.enabled:
            self.port.stopListening()
            self.port = None

    def check_num_packets(self, ip, incoming):
        if self.ips[ip] < 0:
            return True

        max_packets_without_reply = self.community.settings.max_packets_without_reply
        if self.ips[ip] >= (max_packets_without_reply + 1 if incoming else max_packets_without_reply):
            self.community.remove_exit_socket(self.circuit_id, destroy=True)
            self.tunnel_logger.error("too many packets to a destination without a reply, "
                               "removing exit socket with circuit_id %d", self.circuit_id)
            return False

        if incoming:
            self.ips[ip] = -1
        else:
            self.ips[ip] += 1

        return True


class TunnelSettings(object):

    def __init__(self, install_dir=None, tribler_session=None):
        self.tunnel_logger = logging.getLogger('TunnelLogger')

        self.crypto = TunnelCrypto()
        self.socks_listen_ports = range(1080, 1085)

        self.min_circuits = 4
        self.max_circuits = 8
        self.max_relays_or_exits = 100

        self.max_time = 10 * 60
        self.max_time_inactive = 20
        self.max_traffic = 250 * 1024 * 1024

        self.max_packets_without_reply = 50
        self.dht_lookup_interval = 30

        if tribler_session:
            self.become_exitnode = tribler_session.get_tunnel_community_exitnode_enabled()
        else:
            self.become_exitnode = False


class ExitCandidate(object):

    def __init__(self, become_exit):
        self.become_exit = become_exit
        self.creation_time = time.time()


class RoundRobin(object):

    def __init__(self, community):
        self.community = community
        self.index = -1

    def has_options(self, hops):
        return len(self.community.active_data_circuits(hops)) > 0

    def select(self, destination, hops):
        if destination and destination[1] == CIRCUIT_ID_PORT:
            circuit_id = self.community.ip_to_circuit_id(destination[0])
            circuit = self.community.circuits.get(circuit_id, None)

            if circuit and circuit.state == CIRCUIT_STATE_READY and \
               circuit.ctype == CIRCUIT_TYPE_RENDEZVOUS:
                return circuit

        circuit_ids = sorted(self.community.active_data_circuits(hops).keys())

        if not circuit_ids:
            return None

        self.index = (self.index + 1) % len(circuit_ids)
        circuit_id = circuit_ids[self.index]
        return self.community.active_data_circuits()[circuit_id]


class TunnelCommunity(Community):

    def __init__(self, *args, **kwargs):
        super(TunnelCommunity, self).__init__(*args, **kwargs)
        self.tunnel_logger = logging.getLogger('TunnelLogger')

        self.data_prefix = "fffffffe".decode("HEX")
        self.circuits = {}
        self.directions = {}
        self.relay_from_to = {}
        self.relay_session_keys = {}
        self.exit_sockets = {}
        self.circuits_needed = defaultdict(int)
        self.exit_candidates = {}
        self.notifier = None
        self.selection_strategy = RoundRobin(self)
        self.stats = defaultdict(int)
        self.creation_time = time.time()
        self.crawler_mids = ['5e02620cfabea2d2d3bfdc2032f6307136a35e69'.decode('hex'),
                             '43e8807e6f86ef2f0a784fbc8fa21f8bc49a82ae'.decode('hex'),
                             'e79efd8853cef1640b93c149d7b0f067f6ccf221'.decode('hex')]
        self.bittorrent_peers = {}

        self.trsession = self.settings = self.socks_server = None

    def initialize(self, tribler_session=None, settings=None):
        self.trsession = tribler_session
        self.settings = settings if settings else TunnelSettings(tribler_session=tribler_session)

        self.tunnel_logger.info("TunnelCommunity: setting become_exitnode = %s" % self.settings.become_exitnode)

        super(TunnelCommunity, self).initialize()

        assert isinstance(self.settings.crypto, TunnelCrypto), self.settings.crypto

        self.crypto.initialize(self)

        self.dispersy.endpoint.listen_to(self.data_prefix, self.on_data)

        self.register_task("do_circuits", LoopingCall(self.do_circuits)).start(5, now=True)
        self.register_task("do_ping", LoopingCall(self.do_ping)).start(PING_INTERVAL)

        self.socks_server = Socks5Server(self, tribler_session.get_tunnel_community_socks5_listen_ports()
                                         if tribler_session else self.settings.socks_listen_ports)
        self.socks_server.start()

        if self.trsession:
            self.notifier = self.trsession.notifier
            self.trsession.lm.tunnel_community = self

    def self_is_connectable(self):
        return self._dispersy._connection_type == u"public"

    def candidate_is_connectable(self, candidate):
        return candidate.connection_type == u"public"

    def become_exitnode(self):
        return self.settings.become_exitnode

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Sat Jul  4 15:31:17 2015
        # curve: None
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000407b5eb7d25859eee6495ca0e1c14e0bb3c38cc4de5c1bb7d198a3cb6e075833ce59ac0464450e8405a6d9f7cce9824b970eb28259b8bd1f391d44c8dc7c8929014764cdbd5bd20300719a696f39dacd4e8c2dd8240e884a6eeff1734b9e175d28d805461f8a94f5fbc84b5ce1d0f322587522d1a79636301bb0efc1052239837beb88f3aa49b1b19b785296421ece659
        # prv: 241 3081ee0201010448023682a3d2a23725d6c8effc8bccc46ecdd5b613621f536d9b41b6f35a1a4bfca1d8175ba6a2171a05aa6d72b6c51499ea602ab33047e4e93715496aa3f2e3526fd48fb75fb32cb4a00706052b81040027a18195038192000407b5eb7d25859eee6495ca0e1c14e0bb3c38cc4de5c1bb7d198a3cb6e075833ce59ac0464450e8405a6d9f7cce9824b970eb28259b8bd1f391d44c8dc7c8929014764cdbd5bd20300719a696f39dacd4e8c2dd8240e884a6eeff1734b9e175d28d805461f8a94f5fbc84b5ce1d0f322587522d1a79636301bb0efc1052239837beb88f3aa49b1b19b785296421ece659
        # pub-sha1 2b62d6f75a72307897f512ecdd38ec5532c3ebc2
        # prv-sha1 eaf086a8eefac71151337b26f8b04fedaa6650d0
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQHtet9JYWe7mSVyg4cFOC7PDjMTeXB
        # u30Zijy24HWDPOWawEZEUOhAWm2ffM6YJLlw6yglm4vR85HUTI3HyJKQFHZM29W9
        # IDAHGaaW852s1OjC3YJA6ISm7v8XNLnhddKNgFRh+KlPX7yEtc4dDzIlh1ItGnlj
        # YwG7DvwQUiOYN764jzqkmxsZt4UpZCHs5lk=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000407b5eb7d25859eee6495ca0e1c14e0bb3c38cc4de5c1bb7d198a3cb6e075833ce59ac0464450e8405a6d9f7cce9824b970eb28259b8bd1f391d44c8dc7c8929014764cdbd5bd20300719a696f39dacd4e8c2dd8240e884a6eeff1734b9e175d28d805461f8a94f5fbc84b5ce1d0f322587522d1a79636301bb0efc1052239837beb88f3aa49b1b19b785296421ece659".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def initiate_meta_messages(self):
        meta_messages = super(TunnelCommunity, self).initiate_meta_messages()
        for i, mm in enumerate(meta_messages):
            if mm.name == "dispersy-introduction-request":
                meta_messages[i] = Message(self, mm.name, mm.authentication, mm.resolution, mm.distribution,
                                           mm.destination, TunnelIntroductionRequestPayload(),
                                           mm.check_callback, mm.handle_callback)
            elif mm.name == "dispersy-introduction-response":
                meta_messages[i] = Message(self, mm.name, mm.authentication, mm.resolution, mm.distribution,
                                           mm.destination, TunnelIntroductionResponsePayload(),
                                           mm.check_callback, mm.handle_callback)

        return meta_messages + [Message(self, u"cell", NoAuthentication(), PublicResolution(), DirectDistribution(),
                                        CandidateDestination(), CellPayload(), self._generic_timeline_check,
                                        self.on_cell),
                                Message(self, u"create", NoAuthentication(), PublicResolution(), DirectDistribution(),
                                        CandidateDestination(), CreatePayload(), self.check_create, self.on_create),
                                Message(self, u"created", NoAuthentication(), PublicResolution(), DirectDistribution(),
                                        CandidateDestination(), CreatedPayload(), self.check_created, self.on_created),
                                Message(self, u"extend", NoAuthentication(), PublicResolution(), DirectDistribution(),
                                        CandidateDestination(), ExtendPayload(), self.check_extend, self.on_extend),
                                Message(self, u"extended", NoAuthentication(), PublicResolution(), DirectDistribution(),
                                        CandidateDestination(), ExtendedPayload(), self.check_extended,
                                        self.on_extended),
                                Message(self, u"ping", NoAuthentication(), PublicResolution(), DirectDistribution(),
                                        CandidateDestination(), PingPayload(), self._generic_timeline_check,
                                        self.on_ping),
                                Message(self, u"pong", NoAuthentication(), PublicResolution(), DirectDistribution(),
                                        CandidateDestination(), PongPayload(), self.check_pong, self.on_pong),
                                Message(self, u"destroy", MemberAuthentication(), PublicResolution(),
                                        DirectDistribution(), CandidateDestination(), DestroyPayload(),
                                        self.check_destroy, self.on_destroy),
                                Message(self, u"stats-request", MemberAuthentication(), PublicResolution(),
                                        DirectDistribution(), CandidateDestination(), StatsRequestPayload(),
                                        self._generic_timeline_check, self.on_stats_request),
                                Message(self, u"stats-response", MemberAuthentication(), PublicResolution(),
                                        DirectDistribution(), CandidateDestination(), StatsResponsePayload(),
                                        self._generic_timeline_check, self.on_stats_response)]

    def initiate_conversions(self):
        return [DefaultConversion(self), TunnelConversion(self)]

    def unload_community(self):
        self.socks_server.stop()

        # Remove all circuits/relays/exitsockets
        for circuit_id in self.circuits.keys():
            self.remove_circuit(circuit_id, 'unload', destroy=True)
        for circuit_id in self.relay_from_to.keys():
            self.remove_relay(circuit_id, 'unload', destroy=True, both_sides=False)
        for circuit_id in self.exit_sockets.keys():
            self.remove_exit_socket(circuit_id, 'unload', destroy=True)

        super(TunnelCommunity, self).unload_community()

    @property
    def crypto(self):
        return self.settings.crypto

    def get_session_keys(self, keys, direction):
        # increment salt_explicit
        keys[direction + 4] += 1
        return keys[direction], keys[direction + 2], keys[direction + 4]

    @property
    def dispersy_enable_bloom_filter_sync(self):
        return False

    @property
    def dispersy_enable_fast_candidate_walker(self):
        return True

    def _generate_circuit_id(self, neighbour=None):
        circuit_id = random.getrandbits(32)

        # Prevent collisions.
        while circuit_id in self.circuits or (neighbour and (neighbour, circuit_id) in self.relay_from_to):
            circuit_id = random.getrandbits(32)

        return circuit_id

    @call_on_reactor_thread
    def do_circuits(self):
        for circuit_length, num_circuits in self.circuits_needed.items():
            num_to_build = num_circuits - len(self.data_circuits(circuit_length))
            self.tunnel_logger.info("want %d data circuits of length %d", num_to_build, circuit_length)
            for _ in range(num_to_build):
                if not self.create_circuit(circuit_length):
                    self.tunnel_logger.info("circuit creation of %d circuits failed, no need to continue" %
                                             num_to_build)
                    break
        self.do_remove()

    def tunnels_ready(self, hops):
        if hops > 0:
            if self.settings.min_circuits:
                return min(1, len(self.active_data_circuits(hops)) / float(self.settings.min_circuits))
            else:
                return 1 if self.active_data_circuits(hops) else 0
        return 1

    def build_tunnels(self, hops):
        if hops > 0:
            self.circuits_needed[hops] = max(1, self.settings.max_circuits, self.circuits_needed[hops])
            self.do_circuits()

    def do_remove(self):
        # Remove circuits that are inactive / are too old / have transferred too many bytes.
        for key, circuit in self.circuits.items():
            if circuit.last_incoming < time.time() - self.settings.max_time_inactive:
                self.remove_circuit(key, 'no activity')
            elif circuit.creation_time < time.time() - self.settings.max_time:
                self.remove_circuit(key, 'too old')
            elif circuit.bytes_up + circuit.bytes_down > self.settings.max_traffic:
                self.remove_circuit(key, 'traffic limit exceeded')

        # Remove relays that are inactive / are too old / have transferred too many bytes.
        for key, relay in self.relay_from_to.items():
            if relay.last_incoming < time.time() - self.settings.max_time_inactive:
                self.remove_relay(key, 'no activity', both_sides=False)
            elif relay.creation_time < time.time() - self.settings.max_time:
                self.remove_relay(key, 'too old', both_sides=False)
            elif relay.bytes_up + relay.bytes_down > self.settings.max_traffic:
                self.remove_relay(key, 'traffic limit exceeded', both_sides=False)

        # Remove exit sockets that are too old / have transferred too many bytes.
        for circuit_id, exit_socket in self.exit_sockets.items():
            if exit_socket.creation_time < time.time() - self.settings.max_time:
                self.remove_exit_socket(circuit_id, 'too old')
            elif exit_socket.bytes_up + exit_socket.bytes_down > self.settings.max_traffic:
                self.remove_exit_socket(circuit_id, 'traffic limit exceeded')

        # Remove exit_candidates that are not returned as dispersy verified candidates
        current_candidates = set(c.get_member().public_key for c in self.dispersy_yield_verified_candidates())
        ckeys = self.exit_candidates.keys()
        for pubkey in ckeys:
            if pubkey not in current_candidates:
                self.exit_candidates.pop(pubkey)
                self.tunnel_logger.info("Removed candidate from exit_candidates dictionary")

    def create_circuit(self, goal_hops, ctype=CIRCUIT_TYPE_DATA, callback=None, required_endpoint=None, info_hash=None):
        assert required_endpoint is None or isinstance(required_endpoint, tuple), type(required_endpoint)
        assert required_endpoint is None or len(required_endpoint) == 3, required_endpoint
        first_hop = None

        self.tunnel_logger.info("Creating a new circuit of length %d", goal_hops)

        if not required_endpoint:
            for c in self.dispersy_yield_verified_candidates():
                pubkey = c.get_member().public_key
                exit_candidate = self.exit_candidates[pubkey]
                if ctype == CIRCUIT_TYPE_DATA:
                    self.tunnel_logger.info("Look for an exit node to set as required_endpoint for this circuit")
                    if exit_candidate.become_exit:
                        self.tunnel_logger.info("Valid exit candidate found for this circuit")
                        required_endpoint = (c.sock_addr[0], c.sock_addr[1], pubkey)
                        break
                else:
                    self.tunnel_logger.info("Try to find connectable node to set as required_endpoint for circuit")
                    required_endpoint = (c.sock_addr[0], c.sock_addr[1], pubkey)
                    if self.candidate_is_connectable(c) and not exit_candidate.become_exit:
                        # Prefer non exit candidate, because the real exit candidates are scarce, save their bandwidth
                        self.tunnel_logger.info("Connectable non-exit required_endpoint found, stop looking further")
                        break

        # If the number of hops is 1, it should immediately be the required_endpoint hop.
        if goal_hops == 1 and required_endpoint:
            self.tunnel_logger.info("Associate first hop with a candidate and member object")
            first_hop = Candidate((required_endpoint[0], required_endpoint[1]), False)
            first_hop.associate(self.get_member(public_key=required_endpoint[2]))
        else:
            self.tunnel_logger.info("Look for a first hop that is not an exit node and is not used before")
            hops = set([c.first_hop for c in self.circuits.values()])
            for c in self.dispersy_yield_verified_candidates():
                if (c.sock_addr not in hops) and self.crypto.is_key_compatible(c.get_member()._ec) and \
                   (not required_endpoint or c.sock_addr != tuple(required_endpoint[:2])) and \
                   not self.exit_candidates[c.get_member().public_key].become_exit:
                    first_hop = c
                    break

        if not required_endpoint:
            self.tunnel_logger.info("could not create circuit, no available exit-nodes.")
            return False

        if not first_hop:
            self.tunnel_logger.info("could not create circuit, no available relay for first hop.")
            return False

        circuit_id = self._generate_circuit_id(first_hop.sock_addr)
        circuit = Circuit(circuit_id, goal_hops, first_hop.sock_addr, self, ctype, callback,
                          required_endpoint, first_hop.get_member().mid.encode('hex'), info_hash)

        self.request_cache.add(CircuitRequestCache(self, circuit))

        circuit.unverified_hop = Hop(first_hop.get_member()._ec)
        circuit.unverified_hop.address = first_hop.sock_addr
        circuit.unverified_hop.dh_secret, circuit.unverified_hop.dh_first_part = self.crypto.generate_diffie_secret()

        self.tunnel_logger.error("creating circuit %d of %d hops. First hop: %s:%d", circuit_id, circuit.goal_hops,
                           first_hop.sock_addr[0], first_hop.sock_addr[1])

        self.circuits[circuit_id] = circuit

        self.increase_bytes_sent(circuit, self.send_cell([first_hop],
                                                         u"create", (circuit_id,
                                                                     circuit.unverified_hop.node_id,
                                                                     circuit.unverified_hop.node_public_key,
                                                                     circuit.unverified_hop.dh_first_part)))

        _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_CREATED, "%s:%s" %
                                               (first_hop.sock_addr[0], first_hop.sock_addr[1]))
        return circuit_id

    def readd_bittorrent_peers(self):
        for torrent, peers in self.bittorrent_peers.items():
            infohash = torrent.tdef.get_infohash().encode("hex")
            for peer in peers:
                self.tunnel_logger.info("Re-adding peer %s to torrent %s", peer, infohash)
                torrent.add_peer(peer)
            del self.bittorrent_peers[torrent]

    def remove_circuit(self, circuit_id, additional_info='', destroy=False):
        assert isinstance(circuit_id, (long, int)), type(circuit_id)

        if circuit_id in self.circuits:
            self.tunnel_logger.info("removing circuit %d " + additional_info, circuit_id)

            if destroy:
                self.destroy_circuit(circuit_id)

            circuit = self.circuits.pop(circuit_id)
            circuit.destroy()

            affected_peers = self.socks_server.circuit_dead(circuit)
            ltmgr = self.trsession.lm.ltmgr if self.trsession and self.trsession.get_libtorrent() else None
            if ltmgr:
                affected_torrents = {d: affected_peers.intersection(peer.ip for peer in d.handle.get_peer_info())
                                     for d, s in ltmgr.torrents.values() if s == ltmgr.get_session(d.get_hops())}

                for download, peers in affected_torrents.iteritems():
                    if peers:
                        if download not in self.bittorrent_peers:
                            self.bittorrent_peers[download] = peers
                        else:
                            self.bittorrent_peers[download] = peers | self.bittorrent_peers[download]

                # If there are active circuits, add peers immediately. Otherwise postpone.
                if self.active_data_circuits():
                    self.readd_bittorrent_peers()

            return True
        return False

    def remove_relay(self, circuit_id, additional_info='', destroy=False, got_destroy_from=None, both_sides=True):
        # Find other side of relay
        to_remove = [circuit_id]
        if both_sides:
            for k, v in self.relay_from_to.iteritems():
                if circuit_id == v.circuit_id:
                    to_remove.append(k)

        # Send destroy
        if destroy:
            self.destroy_relay(to_remove, got_destroy_from=got_destroy_from)

        for cid in to_remove:
            if cid in self.relay_from_to:
                self.tunnel_logger.warning("Removing relay %d %s", cid, additional_info)
                # Remove the relay
                del self.relay_from_to[cid]
                # Remove old session key
                if cid in self.relay_session_keys:
                    del self.relay_session_keys[cid]
            else:
                self.tunnel_logger.error("Could not remove relay %d %s", circuit_id, additional_info)

    def remove_exit_socket(self, circuit_id, additional_info='', destroy=False):
        if circuit_id in self.exit_sockets:
            if destroy:
                self.destroy_exit_socket(circuit_id)

            # Close socket
            exit_socket = self.exit_sockets.pop(circuit_id)
            if exit_socket.enabled:
                self.tunnel_logger.info("Removing exit socket %d %s", circuit_id, additional_info)
                exit_socket.close()
                # Remove old session key
                if circuit_id in self.relay_session_keys:
                    del self.relay_session_keys[circuit_id]
        else:
            self.tunnel_logger.error("could not remove exit socket %d %s", circuit_id, additional_info)

    def destroy_circuit(self, circuit_id, reason=0):
        if circuit_id in self.circuits:
            sock_addr = self.circuits[circuit_id].first_hop
            self.send_destroy(Candidate(sock_addr, False), circuit_id, reason)
            self.tunnel_logger.info("destroy_circuit %s %s", circuit_id, sock_addr)
        else:
            self.tunnel_logger.error("could not destroy circuit %d %s", circuit_id, reason)

    def destroy_relay(self, circuit_ids, reason=0, got_destroy_from=None):
        relays = {cid_from: (self.relay_from_to[cid_from].circuit_id,
                             self.relay_from_to[cid_from].sock_addr) for cid_from in circuit_ids
                  if cid_from in self.relay_from_to}

        if got_destroy_from and got_destroy_from not in relays.values():
            self.tunnel_logger.error("%s not allowed send destroy for circuit %s",
                                     *reversed(got_destroy_from))
            return

        for cid_from, (cid_to, sock_addr) in relays.iteritems():
            self.tunnel_logger.info("found relay %s -> %s (%s)", cid_from, cid_to, sock_addr)
            if (cid_to, sock_addr) != got_destroy_from:
                self.send_destroy(Candidate(sock_addr, False), cid_to, reason)
                self.tunnel_logger.info("fw destroy to %s %s", cid_to, sock_addr)

    def destroy_exit_socket(self, circuit_id, reason=0):
        if circuit_id in self.exit_sockets:
            sock_addr = self.exit_sockets[circuit_id].sock_addr
            self.send_destroy(Candidate(sock_addr, False), circuit_id, reason)
            self.tunnel_logger.info("destroy_exit_socket %s %s", circuit_id, sock_addr)
        else:
            self.tunnel_logger.error("could not destroy exit socket %d %s", circuit_id, reason)

    def data_circuits(self, hops=None):
        return {cid: c for cid, c in self.circuits.items()
                if c.ctype == CIRCUIT_TYPE_DATA and (hops is None or hops == len(c.hops))}

    def active_data_circuits(self, hops=None):
        return {cid: c for cid, c in self.circuits.items()
                if c.state == CIRCUIT_STATE_READY and c.ctype == CIRCUIT_TYPE_DATA and
                (hops is None or hops == len(c.hops))}

    def is_relay(self, circuit_id):
        return circuit_id > 0 and circuit_id in self.relay_from_to

    def is_circuit(self, circuit_id):
        return circuit_id > 0 and circuit_id in self.circuits

    def is_exit(self, circuit_id):
        return circuit_id > 0 and circuit_id in self.exit_sockets

    def send_cell(self, candidates, message_type, payload):
        meta = self.get_meta_message(message_type)
        message = meta.impl(distribution=(self.global_time,), payload=payload)
        packet = TunnelConversion.convert_to_cell(message.packet)

        return self.send_message(candidates, message_type, packet, message.payload.circuit_id)

    def send_data(self, candidates, circuit_id, dest_address, source_address, data):
        packet = TunnelConversion.encode_data(circuit_id, dest_address, source_address, data)
        return self.send_message(candidates, u"data", packet, circuit_id)

    def send_message(self, candidates, message_type, packet, circuit_id):
        is_data = message_type == u"data"

        if message_type not in [u'create', u'created']:
            plaintext, encrypted = TunnelConversion.split_encrypted_packet(packet, message_type)
            try:
                encrypted = self.crypto_out(circuit_id, encrypted, is_data=is_data)
                packet = plaintext + encrypted

            except CryptoException, e:
                self.tunnel_logger.error(str(e))
                return 0

        return self.send_packet(candidates, message_type, packet)

    def send_packet(self, candidates, message_type, packet):
        if self.dispersy.endpoint.send(candidates, [packet], prefix=self.data_prefix if message_type == u"data" else None):
            self.statistics.increase_msg_count(u"outgoing", message_type, len(candidates))
            self.tunnel_logger.debug("send %s to %s candidates: %s", message_type, len(candidates), map(str, candidates))
            return len(packet)
        return 0

    def send_destroy(self, candidate, circuit_id, reason):
        meta = self.get_meta_message(u"destroy")
        destroy = meta.impl(authentication=(self._my_member,), distribution=(
            self.global_time,), payload=(circuit_id, reason))
        self.send_packet([candidate], meta.name, destroy.packet)

    def relay_cell(self, circuit_id, message_type, message):
        return self.relay_packet(circuit_id, message_type, message.packet)

    def relay_packet(self, circuit_id, message_type, packet):
        next_relay = self.relay_from_to[circuit_id]
        this_relay = self.relay_from_to.get(next_relay.circuit_id, None)

        self.tunnel_logger.debug("Relay %s from %d to %d", message_type, circuit_id, next_relay.circuit_id)

        if this_relay:
            this_relay.last_incoming = time.time()
            self.increase_bytes_received(this_relay, len(packet))

        plaintext, encrypted = TunnelConversion.split_encrypted_packet(packet, message_type)
        try:
            if next_relay.rendezvous_relay:
                decrypted = self.crypto_in(circuit_id, encrypted)
                encrypted = self.crypto_out(next_relay.circuit_id, decrypted)
            else:
                encrypted = self.crypto_relay(circuit_id, encrypted)
            packet = plaintext + encrypted

        except CryptoException, e:
            self.tunnel_logger.error(str(e))
            return False

        packet = TunnelConversion.swap_circuit_id(packet, message_type, circuit_id, next_relay.circuit_id)
        self.increase_bytes_sent(next_relay, self.send_packet([Candidate(next_relay.sock_addr, False)], message_type, packet))
        return True

    def check_create(self, messages):
        for message in messages:
            if self.crypto.key and self.crypto.key.key_to_hash() != message.payload.node_id:
                yield DropMessage(message, "nodeids do not match")
                continue

            if self.crypto.key and self.crypto.key.pub().key_to_bin() != message.payload.node_public_key:
                yield DropMessage(message, "public keys do not match")
                continue

            if self.settings.max_relays_or_exits <= len(self.relay_from_to) + len(self.exit_sockets):
                yield DropMessage(message, "too many relays %d" % (len(self.relay_from_to) + len(self.exit_sockets)))
                continue

            if self._request_cache.has(u"anon-created", message.payload.circuit_id):
                yield DropMessage(message, "already have a request for this circuit_id")
                continue

            yield message

    def check_extend(self, messages):
        for message in messages:
            request = self.request_cache.get(u"anon-created", message.payload.circuit_id)
            if not request:
                yield DropMessage(message, "invalid extend request circuit_id")
                continue

            if not message.payload.node_public_key:
                yield DropMessage(message, "no node public key specified")
                continue

            if not (message.payload.node_addr or message.payload.node_public_key in request.candidates):
                yield DropMessage(message, "node public key not in request candidates and no ip specified")
                continue

            yield message

    def check_created(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            request = self.request_cache.get(u"anon-circuit", circuit_id)
            if not request:
                yield DropMessage(message, "invalid created response circuit_id")
                continue

            yield message

    def check_extended(self, messages):
        for message in messages:
            request = self.request_cache.get(u"anon-circuit", message.payload.circuit_id)
            if not request:
                yield DropMessage(message, "invalid extended response circuit_id")
                continue
            yield message

    def check_pong(self, messages):
        for message in messages:
            request = self.request_cache.get(u"ping", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid ping identifier")
                continue
            yield message

    def check_destroy(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            cand_sock_addr = message.candidate.sock_addr

            if circuit_id in self.relay_from_to:
                pass

            elif circuit_id in self.exit_sockets:
                if cand_sock_addr != self.exit_sockets[circuit_id].sock_addr:
                    yield DropMessage(message, "%s not allowed send destroy", cand_sock_addr)
                    continue

            elif circuit_id in self.circuits:
                if cand_sock_addr != self.circuits[circuit_id].first_hop:
                    yield DropMessage(message, "%s not allowed send destroy", cand_sock_addr)
                    continue

            else:
                yield DropMessage(message, "unknown circuit_id")
                continue

            yield message

    def _ours_on_created_extended(self, circuit, message):
        hop = circuit.unverified_hop

        try:
            shared_secret = self.crypto.verify_and_generate_shared_secret(hop.dh_secret, message.payload.key,
                                                                          message.payload.auth, hop.public_key.key.pk)
            hop.session_keys = self.crypto.generate_session_keys(shared_secret)

        except CryptoException:
            self.remove_circuit(circuit.circuit_id, "error while verifying shared secret, bailing out.")
            return

        circuit.add_hop(hop)
        circuit.unverified_hop = None

        if circuit.state == CIRCUIT_STATE_EXTENDING:
            ignore_candidates = [self.crypto.key_to_bin(hop.public_key) for hop in circuit.hops] + \
                [self.my_member.public_key]
            if circuit.required_endpoint:
                ignore_candidates.append(circuit.required_endpoint[2])

            become_exit = circuit.goal_hops - 1 == len(circuit.hops)
            if become_exit and circuit.required_endpoint:
                # Set the required exit according to the circuit setting (e.g. for linking e2e circuits)
                host, port, pub_key = circuit.required_endpoint
                extend_hop_public_bin = pub_key
                extend_hop_addr = (host, port)

            else:
                # The next candidate is chosen from the returned list of possible candidates
                candidate_list_enc = message.payload.candidate_list
                _, candidate_list = decode(self.crypto.decrypt_str(candidate_list_enc,
                                                                   hop.session_keys[EXIT_NODE],
                                                                   hop.session_keys[EXIT_NODE_SALT]))

                for ignore_candidate in ignore_candidates:
                    if ignore_candidate in candidate_list:
                        candidate_list.remove(ignore_candidate)

                for i in range(len(candidate_list) - 1, -1, -1):
                    public_key = self.crypto.key_from_public_bin(candidate_list[i])
                    if not self.crypto.is_key_compatible(public_key):
                        candidate_list.pop(i)

                pub_key = next(iter(candidate_list), None)
                extend_hop_public_bin = pub_key
                extend_hop_addr = None

            if extend_hop_public_bin:
                extend_hop_public_key = self.dispersy.crypto.key_from_public_bin(extend_hop_public_bin)
                circuit.unverified_hop = Hop(extend_hop_public_key)
                circuit.unverified_hop.dh_secret, circuit.unverified_hop.dh_first_part = \
                    self.crypto.generate_diffie_secret()

                self.tunnel_logger.info("extending circuit %d with %s", circuit.circuit_id,
                                        extend_hop_public_bin.encode('hex'))

                self.increase_bytes_sent(circuit, self.send_cell([Candidate(circuit.first_hop, False)],
                                                                 u"extend",
                                                                 (circuit.circuit_id,
                                                                  circuit.unverified_hop.node_id,
                                                                  circuit.unverified_hop.node_public_key,
                                                                  extend_hop_addr,
                                                                  circuit.unverified_hop.dh_first_part)))

            else:
                self.remove_circuit(circuit.circuit_id, "no candidates to extend, bailing out.")

        elif circuit.state == CIRCUIT_STATE_READY:
            self.request_cache.pop(u"anon-circuit", circuit.circuit_id)
            # Re-add BitTorrent peers, if needed.
            self.readd_bittorrent_peers()

            # Execute callback
            if circuit.callback:
                circuit.callback(circuit)
                circuit.callback = None
        else:
            return

        if self.notifier:
            from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_CREATED, NTFY_EXTENDED
            self.notifier.notify(NTFY_TUNNEL, NTFY_CREATED if len(circuit.hops) == 1 else NTFY_EXTENDED, circuit)

    def on_introduction_request(self, messages):
        exitnode = self.become_exitnode()
        extra_payload = [exitnode]
        super(TunnelCommunity, self).on_introduction_request(messages, extra_payload)
        for message in messages:
            pubkey = message.candidate.get_member().public_key
            self.exit_candidates[pubkey] = ExitCandidate(message.payload.exitnode)

    def create_introduction_request(self, destination, allow_sync, forward=True, is_fast_walker=False):
        exitnode = self.become_exitnode()
        extra_payload = [exitnode]
        super(TunnelCommunity, self).create_introduction_request(destination, allow_sync, forward,
                                                                 is_fast_walker, extra_payload)

    def on_introduction_response(self, messages):
        super(TunnelCommunity, self).on_introduction_response(messages)
        for message in messages:
            pubkey = message.candidate.get_member().public_key
            self.exit_candidates[pubkey] = ExitCandidate(message.payload.exitnode)

    def on_cell(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            self.tunnel_logger.warning("Got %s (%d) from %s, I am %s", message.payload.message_type,
                                     message.payload.circuit_id, message.candidate.sock_addr,
                                     self.my_member)

            if self.is_relay(circuit_id):
                if not self.relay_cell(circuit_id, message.payload.message_type, message):
                    # TODO: if crypto fails for relay messages, call remove_relay
                    pass

            else:
                circuit = self.circuits.get(circuit_id, None)
                packet = message.packet

                if message.payload.message_type not in [u'create', u'created']:
                    plaintext, encrypted = TunnelConversion.split_encrypted_packet(packet, message.name)
                    try:
                        encrypted = self.crypto_in(circuit_id, encrypted)
                        packet = plaintext + encrypted

                    except CryptoException, e:
                        self.tunnel_logger.warning(str(e))

                        # TODO: if crypto fails for other messages, call remove_circuit
                        continue

                self.dispersy.on_incoming_packets([(message.candidate, TunnelConversion.convert_from_cell(packet))],
                                                  False, source=u"circuit_%d" % circuit_id)

                if circuit:
                    circuit.beat_heart()
                    self.increase_bytes_received(circuit, len(message.packet))

    def on_create(self, messages):
        for message in messages:
            candidate = message.candidate
            circuit_id = message.payload.circuit_id

            self.directions[circuit_id] = EXIT_NODE
            self.tunnel_logger.info('TunnelCommunity: we joined circuit %d with neighbour %s',
                                    circuit_id, candidate.sock_addr)

            shared_secret, Y, AUTH = self.crypto.generate_diffie_shared_secret(message.payload.key)
            self.relay_session_keys[circuit_id] = self.crypto.generate_session_keys(shared_secret)

            candidates = {}
            for c in self.dispersy_yield_verified_candidates():
                pubkey = c.get_member().public_key
                vc = self.exit_candidates[pubkey]
                if vc.become_exit:
                    # Exit nodes are chosen by the circuit initiator, we decided not to use exit nodes as normal relay
                    continue

                candidates[pubkey] = c
                if len(candidates) >= 4:
                    break

            self.request_cache.add(CreatedRequestCache(self, circuit_id, candidate, candidates))
            candidate_mid = 0
            if candidate.get_member() is not None:
                candidate_mid = candidate.get_member().mid.encode('hex')
            self.exit_sockets[circuit_id] = TunnelExitSocket(circuit_id, self, candidate.sock_addr, candidate_mid)

            if self.notifier:
                from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_JOINED
                self.notifier.notify(NTFY_TUNNEL, NTFY_JOINED, candidate.sock_addr, circuit_id)

            candidate_list_enc = self.crypto.encrypt_str(encode(candidates.keys()),
                                                         *self.get_session_keys(self.relay_session_keys[circuit_id], EXIT_NODE))
            self.send_cell([candidate], u"created", (circuit_id, Y, AUTH, candidate_list_enc))

    def on_created(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            self.directions[circuit_id] = ORIGINATOR

            request = self.request_cache.get(u"anon-circuit", circuit_id)
            if request.should_forward:
                self.request_cache.pop(u"anon-circuit", circuit_id)

                self.tunnel_logger.info("Got CREATED message forward as EXTENDED to origin.")

                self.relay_from_to[request.to_circuit_id] = forwarding_relay = RelayRoute(request.from_circuit_id,
                                                                                          request.candidate_sock_addr,
                                                                                          mid=request.candidate_mid)

                self.relay_from_to[request.from_circuit_id] = RelayRoute(request.to_circuit_id,
                                                                         request.to_candidate_sock_addr,
                                                                         mid=request.to_candidate_mid)

                self.relay_session_keys[request.to_circuit_id] = self.relay_session_keys[request.from_circuit_id]

                self.directions[request.from_circuit_id] = EXIT_NODE
                self.remove_exit_socket(request.from_circuit_id)

                self.send_cell([Candidate(forwarding_relay.sock_addr, False)], u"extended", (forwarding_relay.circuit_id,
                                                                                  message.payload.key,
                                                                                  message.payload.auth,
                                                                                  message.payload.candidate_list))
            else:
                circuit = self.circuits[circuit_id]
                self._ours_on_created_extended(circuit, message)

    def on_extend(self, messages):
        for message in messages:
            candidate = message.candidate
            circuit_id = message.payload.circuit_id
            request = self.request_cache.pop(u"anon-created", circuit_id)

            if message.payload.node_public_key in request.candidates:
                extend_candidate = request.candidates[message.payload.node_public_key]
                extend_candidate_mid = extend_candidate.get_member().mid.encode('hex')
            else:
                extend_candidate = Candidate(message.payload.node_addr, False)
                extend_candidate_mid = 0

            # key = self.crypto.key_from_public_bin(message.payload.node_public_key)
            # extend_candidate_mid = key.key_to_hash().encode('hex')

            self.tunnel_logger.info("on_extend send CREATE for circuit (%s, %d) to %s:%d", candidate.sock_addr,
                                    circuit_id,
                                    extend_candidate.sock_addr[0],
                                    extend_candidate.sock_addr[1])

            to_circuit_id = self._generate_circuit_id(extend_candidate.sock_addr)

            candidate_mid = 0
            if candidate.get_member():
                candidate_mid = candidate.get_member().mid.encode('hex')

            self.tunnel_logger.info("extending circuit, got candidate with IP %s:%d from cache",
                                    *extend_candidate.sock_addr)

            self.request_cache.add(ExtendRequestCache(self, to_circuit_id, circuit_id,
                                                      candidate.sock_addr, candidate_mid,
                                                      extend_candidate.sock_addr, extend_candidate_mid))


            self.increase_bytes_sent(to_circuit_id, self.send_cell([extend_candidate],
                                                                    u"create", (to_circuit_id,
                                                                                message.payload.node_id,
                                                                                message.payload.node_public_key,
                                                                                message.payload.key)))

    def on_extended(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            circuit = self.circuits[circuit_id]
            self._ours_on_created_extended(circuit, message)

    @call_on_reactor_thread
    def on_data(self, sock_addr, packet):
        # If its our circuit, the messenger is the candidate assigned to that circuit and the DATA's destination
        # is set to the zero-address then the packet is from the outside world and addressed to us from.

        message_type = u'data'
        circuit_id = TunnelConversion.get_circuit_id(packet, message_type)

        self.tunnel_logger.debug("Got data (%d) from %s", circuit_id, sock_addr)

        if self.is_relay(circuit_id):
            self.relay_packet(circuit_id, message_type, packet)

        else:
            plaintext, encrypted = TunnelConversion.split_encrypted_packet(packet, message_type)

            try:
                encrypted = self.crypto_in(circuit_id, encrypted, is_data=True)

            except CryptoException, e:
                self.tunnel_logger.warning(str(e))
                return

            packet = plaintext + encrypted
            circuit_id, destination, origin, data = TunnelConversion.decode_data(packet)

            circuit = self.circuits.get(circuit_id, None)
            if circuit and origin and sock_addr == circuit.first_hop:
                circuit.beat_heart()
                self.increase_bytes_received(circuit, len(packet))

                if TunnelConversion.could_be_dispersy(data):
                    self.tunnel_logger.debug("Giving incoming data packet to dispersy")
                    self.dispersy.on_incoming_packets([(Candidate(origin, False),
                                                        data[TUNNEL_PREFIX_LENGHT:])],
                                                      False, source=u"circuit_%d" % circuit_id)
                else:
                    anon_seed = circuit.ctype == CIRCUIT_TYPE_RP
                    self.socks_server.on_incoming_from_tunnel(self, circuit, origin, data, anon_seed)

            # It is not our circuit so we got it from a relay, we need to EXIT it!
            else:
                self.tunnel_logger.debug("data for circuit %d exiting tunnel (%s)", circuit_id, destination)
                if destination != ('0.0.0.0', 0):
                    self.exit_data(circuit_id, sock_addr, destination, data)
                else:
                    self.tunnel_logger.warning("cannot exit data, destination is 0.0.0.0:0")

    def on_ping(self, messages):
        for message in messages:
            self.send_cell([message.candidate], u"pong", (message.payload.circuit_id, message.payload.identifier))
            self.tunnel_logger.info("Got ping from %s", message.candidate)

    def on_pong(self, messages):
        for message in messages:
            self.request_cache.pop(u"ping", message.payload.identifier)
            self.tunnel_logger.info("Got pong from %s", message.candidate)

    def do_ping(self):
        # Ping circuits. Pings are only sent to the first hop, subsequent hops will relay the ping.
        for circuit in self.circuits.values():
            if circuit.state == CIRCUIT_STATE_READY and circuit.ctype != CIRCUIT_TYPE_RENDEZVOUS:
                cache = self.request_cache.add(PingRequestCache(self, circuit))
                self.increase_bytes_sent(circuit, self.send_cell([Candidate(circuit.first_hop, False)],
                                                                 u"ping", (circuit.circuit_id, cache.number)))

    def on_destroy(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            cand_sock_addr = message.candidate.sock_addr
            self.tunnel_logger.info("Got destroy from %s for circuit %s", message.candidate, circuit_id)

            if circuit_id in self.relay_from_to:
                self.remove_relay(circuit_id, "Got destroy", True, (circuit_id, cand_sock_addr))

            elif circuit_id in self.exit_sockets:
                self.tunnel_logger.info("Got an exit socket %s %s", circuit_id, cand_sock_addr)
                self.remove_exit_socket(circuit_id, "Got destroy")

            elif circuit_id in self.circuits:
                self.tunnel_logger.info("Got a circuit %s %s", circuit_id, cand_sock_addr)
                self.remove_circuit(circuit_id, "Got destroy")

    def on_stats_request(self, messages):
        for request in messages:
            if request.candidate.get_member().mid in self.crawler_mids:
                meta = self.get_meta_message(u"stats-response")
                stats = dict(self.stats)
                stats['uptime'] = time.time() - self.creation_time
                response = meta.impl(authentication=(self._my_member,), distribution=(
                    self.global_time,), payload=(request.payload.identifier, stats))
                self.send_packet([request.candidate], u"stats-response", response.packet)
            else:
                self.tunnel_logger.error("Got stats request from unknown crawler %s", request.candidate.sock_addr)

    def on_stats_response(self, messages):
        for message in messages:
            request = self.request_cache.get(u"stats", message.payload.identifier)
            if not request:
                self.tunnel_logger.error("Got unexpected stats response from %s", message.candidate.sock_addr)
                continue

            request.handler(message.candidate, message.payload.stats)
            self.tunnel_logger.info("Received stats response %s", message.payload.stats)

    def do_stats(self, candidate, handler):
        cache = self.request_cache.add(StatsRequestCache(self, handler))
        meta = self.get_meta_message(u"stats-request")
        request = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(cache.number,))
        self.send_packet([candidate], u"stats-request", request.packet)

    def exit_data(self, circuit_id, sock_addr, destination, data):
        if not self.become_exitnode() and not TunnelConversion.could_be_dispersy(data):
            self.tunnel_logger.error("Dropping data packets, refusing to be an exit node for data")

        elif circuit_id in self.exit_sockets:
            if not self.exit_sockets[circuit_id].enabled:
                # Check that we got the correct circuit_id, but from a wrong IP.
                if sock_addr[0] == self.exit_sockets[circuit_id].sock_addr[0]:
                    self.exit_sockets[circuit_id].enable()
                else:
                    self._logger.error("Dropping outbound relayed packet: IP's are %s != %s", str(sock_addr), str(self.exit_sockets[circuit_id].sock_addr))
            try:
                self.exit_sockets[circuit_id].sendto(data, destination)
            except:
                self.tunnel_logger.error("Dropping data packets while EXITing")
        else:
            self.tunnel_logger.error("Dropping data packets with unknown circuit_id")

    def crypto_out(self, circuit_id, content, is_data=False):
        circuit = self.circuits.get(circuit_id, None)
        if circuit:
            if circuit and is_data and circuit.ctype in [CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP]:
                direction = int(circuit.ctype == CIRCUIT_TYPE_RP)
                content = self.crypto.encrypt_str(content, *self.get_session_keys(circuit.hs_session_keys, direction))

            for hop in reversed(circuit.hops):
                content = self.crypto.encrypt_str(content, *self.get_session_keys(hop.session_keys, EXIT_NODE))
            return content

        elif circuit_id in self.relay_session_keys:
            return self.crypto.encrypt_str(content,
                                           *self.get_session_keys(self.relay_session_keys[circuit_id], ORIGINATOR))

        raise CryptoException("Don't know how to encrypt outgoing message for circuit_id %d" % circuit_id)

    def crypto_in(self, circuit_id, content, is_data=False):
        circuit = self.circuits.get(circuit_id, None)
        if circuit:
            if len(circuit.hops) > 0:
                # Remove all the encryption layers
                layer = 0
                for hop in self.circuits[circuit_id].hops:
                    layer += 1
                    try:
                        content = self.crypto.decrypt_str(content,
                                                          hop.session_keys[ORIGINATOR],
                                                          hop.session_keys[ORIGINATOR_SALT])
                    except InvalidTag as e:
                        raise CryptoException("Got exception %r when trying to remove encryption layer %s "
                                              "for message: %r received for circuit_id: %s, is_data: %i, "
                                              "circuit_hops: %r" % (e, layer, content, circuit_id, is_data, circuit.hops
                                                                    ))

                if is_data and circuit.ctype in [CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP]:
                    direction = int(circuit.ctype != CIRCUIT_TYPE_RP)
                    direction_salt = direction + 2
                    content = self.crypto.decrypt_str(content,
                                                      circuit.hs_session_keys[direction],
                                                      circuit.hs_session_keys[direction_salt])
                return content

            else:
                raise CryptoException("Error decrypting message for circuit %d, circuit is set to 0 hops.")

        elif circuit_id in self.relay_session_keys:
            return self.crypto.decrypt_str(content,
                                           self.relay_session_keys[circuit_id][EXIT_NODE],
                                           self.relay_session_keys[circuit_id][EXIT_NODE_SALT])

        raise CryptoException("Received message for unknown circuit ID: %d" % circuit_id)

    def crypto_relay(self, circuit_id, content):
        direction = self.directions[circuit_id]
        if direction == ORIGINATOR:
            return self.crypto.encrypt_str(content,
                                           *self.get_session_keys(self.relay_session_keys[circuit_id], ORIGINATOR))
        elif direction == EXIT_NODE:
            try:
                return self.crypto.decrypt_str(content,
                                               self.relay_session_keys[circuit_id][EXIT_NODE],
                                               self.relay_session_keys[circuit_id][EXIT_NODE_SALT])
            except InvalidTag:
                # Reasons that can cause this:
                # - The introductionpoint circuit is extended with a candidate
                # that is already part of the circuit, causing a crypto error.
                # Should not happen anyway, thorough analysis of the debug log
                # may reveal why and how this candidate is discovered.
                #
                # - The pubkey of the introduction point changed (e.g. due to a
                # restart), while other peers in the network are still exchanging
                # the old key information.
                #- A hostile peer may have forged the key of a candidate while
                # pexing information about candidates, thus polluting the network
                # with wrong information. I doubt this is the case but it's
                # possible. :)
                # (from https://github.com/Tribler/tribler/issues/1932#issuecomment-182035383)

                self._logger.warning("Could not decrypt message:\n"
                                     "  direction %s\n"
                                     "  circuit_id: %r\n"
                                     "  content: : %r\n"
                                     "  Possibly corrupt data?",
                                     direction, circuit_id, content)

        raise CryptoException("Direction must be either ORIGINATOR or EXIT_NODE")

    def increase_bytes_sent(self, obj, num_bytes):
        if isinstance(obj, Circuit):
            obj.bytes_up += num_bytes
            self.stats['bytes_up'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_BYTES_SENT, "%s:%s" %
                                                   (obj.first_hop[0], obj.first_hop[1]), num_bytes)
        elif isinstance(obj, RelayRoute):
            obj.bytes_up += num_bytes
            self.stats['bytes_relay_up'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_RELAY_BYTES_SENT, "%s:%s" %
                                                   (obj.sock_addr[0], obj.sock_addr[1]), num_bytes)
        elif isinstance(obj, TunnelExitSocket):
            obj.bytes_up += num_bytes
            self.stats['bytes_exit'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT, "%s:%s" %
                                                   (obj.sock_addr[0], obj.sock_addr[1]), num_bytes)

    def increase_bytes_received(self, obj, num_bytes):
        if isinstance(obj, Circuit):
            obj.bytes_down += num_bytes
            self.stats['bytes_down'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_BYTES_RECEIVED, "%s:%s" %
                                                   (obj.first_hop[0], obj.first_hop[1]), num_bytes)
        elif isinstance(obj, RelayRoute):
            obj.bytes_down += num_bytes
            self.stats['bytes_relay_down'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_RELAY_BYTES_RECEIVED, "%s:%s" %
                                                   (obj.sock_addr[0], obj.sock_addr[1]), num_bytes)
        elif isinstance(obj, TunnelExitSocket):
            obj.bytes_down += num_bytes
            self.stats['bytes_enter'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, "%s:%s" %
                                                   (obj.sock_addr[0], obj.sock_addr[1]), num_bytes)
