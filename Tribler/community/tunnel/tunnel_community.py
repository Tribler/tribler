# Written by Egbert Bouman
# Based on ProxyCommunity by Chris Tanaskoski and Rutger Plak (crypto)

import time
import random
import logging

from traceback import print_exc
from collections import defaultdict

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.task import LoopingCall

from Tribler.Core.Utilities.encoding import encode, decode

from Tribler.community.tunnel import (CIRCUIT_STATE_READY, CIRCUIT_STATE_EXTENDING, ORIGINATOR,
                                      PING_INTERVAL, EXIT_NODE, CIRCUIT_TYPE_DATA, CIRCUIT_TYPE_RP,
                                      CIRCUIT_TYPE_RENDEZVOUS, EXIT_NODE_SALT, ORIGINATOR_SALT)
from Tribler.community.tunnel.conversion import TunnelConversion
from Tribler.community.tunnel.payload import (CellPayload, CreatePayload, CreatedPayload, ExtendPayload,
                                              ExtendedPayload, DestroyPayload, PongPayload, PingPayload,
                                              StatsRequestPayload, StatsResponsePayload)
from Tribler.community.tunnel.routing import Circuit, Hop, RelayRoute
from Tribler.community.tunnel.tests.test_libtorrent import LibtorrentTest
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.community.tunnel.crypto.tunnelcrypto import TunnelCrypto, CryptoException

from Tribler.dispersy.authentication import NoAuthentication, MemberAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.endpoint import TUNNEL_PREFIX_LENGHT
from Tribler.dispersy.message import Message, DropMessage
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.dispersy.requestcache import NumberCache, RandomNumberCache
from Tribler.community.bartercast4.statistics import BartercastStatisticTypes, _barter_statistics


class CircuitRequestCache(NumberCache):

    def __init__(self, community, circuit, retry):
        super(CircuitRequestCache, self).__init__(community.request_cache, u"anon-circuit", circuit.circuit_id)
        self.community = community
        self.circuit = circuit
        self.retry = retry

    def on_timeout(self):
        if self.circuit.state != CIRCUIT_STATE_READY:
            reason = 'timeout on CircuitRequestCache, state = %s, candidate = %s' % (
                self.circuit.state, self.circuit.first_hop)
            self.community.remove_circuit(self.number, reason)
            if self.retry:
                self.retry()


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
        self.circuit = circuit
        self.community = community

    @property
    def timeout_delay(self):
        return PING_INTERVAL + 5

    def on_timeout(self):
        if self.circuit.last_incoming < time.time() - self.timeout_delay:
            self._logger.debug("PingRequestCache: no response on ping, circuit %d timed out", self.circuit.circuit_id)
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
        self._logger = logging.getLogger(self.__class__.__name__)

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
                try:
                    self.transport.write(data, destination)
                except Exception, e:
                    self._logger.error("Failed to write data to transport: %s", str(destination).encode("HEX"))
                    raise

                self.community.increase_bytes_sent(self, len(data))
            else:
                self._logger.error("dropping forbidden packets from exit socket with circuit_id %d", self.circuit_id)

    def datagramReceived(self, data, source):
        self.community.increase_bytes_received(self, len(data))
        if self.check_num_packets(source, True):
            if TunnelConversion.is_allowed(data):
                self.tunnel_data(source, data)
            else:
                self._logger.warning("dropping forbidden packets to exit socket with circuit_id %d", self.circuit_id)

    def tunnel_data(self, source, data):
        self.community.tunnel_data_to_origin(self.circuit_id, self.sock_addr, source, data)

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
            self._logger.error("too many packets to a destination without a reply, "
                               "removing exit socket with circuit_id %d", self.circuit_id)
            return False

        if incoming:
            self.ips[ip] = -1
        else:
            self.ips[ip] += 1

        return True


class TunnelSettings(object):

    def __init__(self, install_dir=None):
        self.circuit_length = 3
        self.crypto = TunnelCrypto()
        self.socks_listen_ports = range(1080, 1085)
        self.do_test = True

        self.min_circuits = 4
        self.max_circuits = 8
        self.max_relays_or_exits = 100

        self.max_time = 10 * 60
        self.max_time_inactive = 20
        self.max_traffic = 55 * 1024 * 1024

        self.max_packets_without_reply = 50


class RoundRobin(object):

    def __init__(self, community):
        self.community = community
        self.index = -1

    def has_options(self, hops):
        return len(self.community.active_data_circuits(hops)) > 0

    def select(self, destination, hops):
        if destination and destination[1] == 1024:
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

        self.data_prefix = "fffffffe".decode("HEX")
        self.circuits = {}
        self.directions = {}
        self.relay_from_to = {}
        self.relay_session_keys = {}
        self.waiting_for = set()
        self.exit_sockets = {}
        self.circuits_needed = {}
        self.notifier = None
        self.made_anon_session = False
        self.selection_strategy = RoundRobin(self)
        self.stats = defaultdict(int)
        self.creation_time = time.time()
        self.crawler_mids = ['5e02620cfabea2d2d3bfdc2032f6307136a35e69'.decode('hex'),
                             '43e8807e6f86ef2f0a784fbc8fa21f8bc49a82ae'.decode('hex'),
                             'e79efd8853cef1640b93c149d7b0f067f6ccf221'.decode('hex')]
        self.bittorrent_peers = {}

        self.trsession = self.settings = self.socks_server = self.libtorrent_test = None

    def initialize(self, tribler_session=None, settings=None):
        super(TunnelCommunity, self).initialize()

        self.trsession = tribler_session
        self.settings = settings if settings else TunnelSettings()

        assert isinstance(self.settings.crypto, TunnelCrypto), self.settings.crypto

        self.crypto.initialize(self)

        self.dispersy.endpoint.listen_to(self.data_prefix, self.on_data)

        self.start_download_test()

        self.register_task("do_circuits", LoopingCall(self.do_circuits)).start(5, now=True)
        self.register_task("do_ping", LoopingCall(self.do_ping)).start(PING_INTERVAL)

        self.socks_server = Socks5Server(self, tribler_session.get_tunnel_community_socks5_listen_ports()
                                         if tribler_session else self.settings.socks_listen_ports)
        self.socks_server.start()

        if self.trsession:
            from Tribler.Core.CacheDB.Notifier import Notifier
            self.notifier = Notifier.getInstance()
            self.trsession.lm.tunnel_community = self

    def start_download_test(self):
        if self.trsession and self.trsession.get_libtorrent() and self.settings.do_test:
            self.libtorrent_test = LibtorrentTest(self, self.trsession)
            if not self.libtorrent_test.has_completed_before():
                self._logger.debug("Scheduling Anonymous LibTorrent download")
                self.register_task("start_test", reactor.callLater(
                    60, lambda: reactor.callInThread(self.libtorrent_test.start)))
                return True
        return False

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Fri Jan 02 19:44:50 2015
        # curve: NID_sect571r1
        # 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000403ab6c5ddea44f806e3fc581ea90cc380d735d2c24ca87b3a68cdf1f95de50010aeff312344eedcae1bb96038db160be4b31a20289023251a2ad88b1f18bde0f14049843f3a35df5017630a445e63bb5005621c04c9b7ba8ca8ccebe567b355b6b21d846199bd8dcc9e7048dc59bf3f1ab70372f19e85d3c2133f56579fa5108840f52ff4ea3e41906623c1d6e8e2eaf
        # pub-sha1 28bad8f1722de818700228c471ab0d7786736c05
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQDq2xd3qRPgG4/xYHqkMw4DXNdLCTK
        # h7OmjN8fld5QAQrv8xI0Tu3K4buWA42xYL5LMaICiQIyUaKtiLHxi94PFASYQ/Oj
        # XfUBdjCkReY7tQBWIcBMm3uoyozOvlZ7NVtrIdhGGZvY3MnnBI3Fm/Pxq3A3Lxno
        # XTwhM/VlefpRCIQPUv9Oo+QZBmI8HW6OLq8=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403ab6c5ddea44f806e3fc581ea90cc380d735d2c24ca87b3a68cdf1f95de50010aeff312344eedcae1bb96038db160be4b31a20289023251a2ad88b1f18bde0f14049843f3a35df5017630a445e63bb5005621c04c9b7ba8ca8ccebe567b355b6b21d846199bd8dcc9e7048dc59bf3f1ab70372f19e85d3c2133f56579fa5108840f52ff4ea3e41906623c1d6e8e2eaf".decode(
            "HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def initiate_meta_messages(self):
        return super(TunnelCommunity, self).initiate_meta_messages() + \
            [Message(self, u"cell", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), CellPayload(), self._generic_timeline_check, self.on_cell),
                Message(self, u"create", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), CreatePayload(), self.check_create, self.on_create),
                Message(self, u"created", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), CreatedPayload(), self.check_created, self.on_created),
                Message(self, u"extend", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), ExtendPayload(), self.check_extend, self.on_extend),
                Message(self, u"extended", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), ExtendedPayload(), self.check_extended, self.on_extended),
                Message(self, u"ping", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), PingPayload(), self._generic_timeline_check, self.on_ping),
                Message(self, u"pong", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), PongPayload(), self.check_pong, self.on_pong),
                Message(self, u"destroy", MemberAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), DestroyPayload(), self._generic_timeline_check,
                        self.on_destroy),
                Message(self, u"stats-request", MemberAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), StatsRequestPayload(), self._generic_timeline_check,
                        self.on_stats_request),
                Message(self, u"stats-response", MemberAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), StatsResponsePayload(), self._generic_timeline_check,
                        self.on_stats_response)]

    def initiate_conversions(self):
        return [DefaultConversion(self), TunnelConversion(self)]

    def unload_community(self):
        self.socks_server.stop()

        # Remove all circuits/relays/exitsockets
        for circuit_id in self.circuits.keys():
            self.remove_circuit(circuit_id, destroy=True)
        for circuit_id in self.relay_from_to.keys():
            self.remove_relay(circuit_id, destroy=True, both_sides=False)
        for circuit_id in self.exit_sockets.keys():
            self.remove_exit_socket(circuit_id, destroy=True)

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

    def do_circuits(self):
        for circuit_length, num_circuits in self.circuits_needed.items():
            num_to_build = num_circuits - sum([1 for c in self.circuits.itervalues() if c.goal_hops == circuit_length])
            self._logger.debug("want %d circuits of length %d", num_to_build, circuit_length)

            for _ in range(num_to_build):
                try:
                    if not self.create_circuit(circuit_length):
                        break
                except:
                    self._logger.exception("Error creating circuit while running do_circuits")

        self.do_remove()

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

    def create_circuit(self, goal_hops, ctype=CIRCUIT_TYPE_DATA, callback=None, max_retries=0, required_exit=None):
        assert required_exit is None or isinstance(required_exit, tuple), type(required_exit)
        assert required_exit is None or len(required_exit) == 3, required_exit
        retry_lambda = first_hop = None

        if max_retries > 0:
            retry_lambda = lambda h = goal_hops, t = ctype, c = callback, r = max_retries - 1, e = required_exit: \
                self.create_circuit(h, t, c, r, e)

        hops = set([c.first_hop for c in self.circuits.values()])
        for c in self.dispersy_yield_verified_candidates():
            if (c.sock_addr not in hops) and self.crypto.is_key_compatible(c.get_member()._ec) and \
               (not required_exit or c.sock_addr != tuple(required_exit[:2])):
                first_hop = c
                break

        if not first_hop:
            if retry_lambda:
                self._logger.info("could not create circuit, no available hops will retry in 5 seconds.")
                self.register_task(retry_lambda, reactor.callLater(5, retry_lambda))
            else:
                self._logger.info("could not create circuit, no available hops.")
            return False

        circuit_id = self._generate_circuit_id(first_hop.sock_addr)
        circuit = Circuit(circuit_id, goal_hops, first_hop.sock_addr, self, ctype, callback, required_exit, first_hop._association.mid.encode('hex'))

        self.request_cache.add(CircuitRequestCache(self, circuit, retry_lambda))

        circuit.unverified_hop = Hop(first_hop.get_member()._ec)
        circuit.unverified_hop.address = first_hop.sock_addr
        circuit.unverified_hop.dh_secret, circuit.unverified_hop.dh_first_part = self.crypto.generate_diffie_secret()

        self._logger.info("creating circuit %d of %d hops. First hop: %s:%d", circuit_id,
                          circuit.goal_hops, first_hop.sock_addr[0], first_hop.sock_addr[1])

        self.circuits[circuit_id] = circuit
        self.waiting_for.add(circuit_id)

        self.increase_bytes_sent(circuit, self.send_cell([first_hop], u"create", (circuit_id,
                                                                                  circuit.unverified_hop.node_id,
                                                                                  circuit.unverified_hop.node_public_key,
                                                                                  circuit.unverified_hop.dh_first_part)))

        return True

    def readd_bittorrent_peers(self):
        for torrent, peers in self.bittorrent_peers.items():
            infohash = torrent.tdef.get_infohash().encode("hex")
            for peer in peers:
                self._logger.debug("Re-adding peer %s to torrent %s", peer, infohash)
                torrent.add_peer(peer)
            del self.bittorrent_peers[torrent]

    def remove_circuit(self, circuit_id, additional_info='', destroy=False, rebuild=False):
        assert isinstance(circuit_id, (long, int)), type(circuit_id)

        if circuit_id in self.circuits:
            self._logger.debug("removing circuit %d " + additional_info, circuit_id)

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
                self._logger.warning("Removing relay %d %s", cid, additional_info)
                # Remove the relay
                del self.relay_from_to[cid]
                # Remove old session key
                if cid in self.relay_session_keys:
                    del self.relay_session_keys[cid]
            else:
                self._logger.error("Could not remove relay %d %s", circuit_id, additional_info)

    def remove_exit_socket(self, circuit_id, additional_info='', destroy=False):
        if circuit_id in self.exit_sockets:
            if destroy:
                self.destroy_exit_socket(circuit_id)
            # Close socket
            exit_socket = self.exit_sockets.pop(circuit_id)
            if exit_socket.enabled:
                self._logger.info("Removing exit socket %d %s", circuit_id, additional_info)
                exit_socket.close()
                # Remove old session key
                if circuit_id in self.relay_session_keys:
                    del self.relay_session_keys[circuit_id]
            return
        self._logger.error("could not remove exit socket %d %s", circuit_id, additional_info)

    def destroy_circuit(self, circuit_id, reason=0):
        if circuit_id in self.circuits:
            sock_addr = self.circuits[circuit_id].first_hop
            self.send_destroy(Candidate(sock_addr, False), circuit_id, reason)
            self._logger.debug("destroy_circuit %s %s", circuit_id, sock_addr)

    def destroy_relay(self, circuit_ids, reason=0, got_destroy_from=None):
        relays = {cid_from: (self.relay_from_to[cid_from].circuit_id,
                             self.relay_from_to[cid_from].sock_addr) for cid_from in circuit_ids
                  if cid_from in self.relay_from_to}

        if got_destroy_from and got_destroy_from not in relays.values():
            self._logger.error("%s not allowed send destroy for circuit %s",
                               *reversed(got_destroy_from))
            return

        for cid_from, (cid_to, sock_addr) in relays.iteritems():
            self._logger.debug("found relay %s -> %s (%s)", cid_from, cid_to, sock_addr)
            if (cid_to, sock_addr) != got_destroy_from:
                self.send_destroy(Candidate(sock_addr, False), cid_to, reason)
                self._logger.debug("fw destroy to %s %s", cid_to, sock_addr)

    def destroy_exit_socket(self, circuit_id, reason=0):
        if circuit_id in self.exit_sockets:
            sock_addr = self.exit_sockets[circuit_id].sock_addr
            self.send_destroy(Candidate(sock_addr, False), circuit_id, reason)
            self._logger.debug("destroy_exit_socket %s %s", circuit_id, sock_addr)

    def active_data_circuits(self, hops=None):
        return {cid: c for cid, c in self.circuits.items()
                if c.state == CIRCUIT_STATE_READY and c.ctype == CIRCUIT_TYPE_DATA and
                (hops is None or hops == len(c.hops))}

    def is_relay(self, circuit_id):
        return circuit_id > 0 and circuit_id in self.relay_from_to and not circuit_id in self.waiting_for

    def send_cell(self, candidates, message_type, payload):
        meta = self.get_meta_message(message_type)
        message = meta.impl(distribution=(self.global_time,), payload=payload)
        packet = TunnelConversion.convert_to_cell(message.packet)

        plaintext, encrypted = TunnelConversion.split_encrypted_packet(packet, u'cell')
        if message_type not in [u'create', u'created']:
            try:
                encrypted = self.crypto_out(message.payload.circuit_id, encrypted)
            except CryptoException, e:
                self._logger.error(str(e))
                return 0
        packet = plaintext + encrypted

        return self.send_packet(candidates, message_type, packet)

    def send_data(self, candidates, message_type, packet):
        circuit_id, _, _, _ = TunnelConversion.decode_data(packet)

        plaintext, encrypted = TunnelConversion.split_encrypted_packet(packet, message_type)
        try:
            encrypted = self.crypto_out(circuit_id, encrypted, is_data=True)
        except CryptoException, e:
            self._logger.error(str(e))
            return 0
        packet = plaintext + encrypted

        return self.send_packet(candidates, u'data', packet)

    def send_packet(self, candidates, message_type, packet):
        self.dispersy.endpoint.send(candidates, [packet], prefix=self.data_prefix if message_type == u"data" else None)
        self.statistics.increase_msg_count(u"outgoing", message_type, len(candidates))
        self._logger.debug("send %s to %s candidates: %s", message_type, len(candidates), map(str, candidates))
        return len(packet)

    def send_destroy(self, candidate, circuit_id, reason):
        meta = self.get_meta_message(u"destroy")
        destroy = meta.impl(authentication=(self._my_member,), distribution=(
            self.global_time,), payload=(circuit_id, reason))
        self.send_packet([candidate], meta.name, destroy.packet)

    def relay_cell(self, circuit_id, message_type, message):
        return self.relay_packet(circuit_id, message_type, message.packet)

    def relay_packet(self, circuit_id, message_type, packet):
        if self.is_relay(circuit_id):
            next_relay = self.relay_from_to[circuit_id]
            this_relay = self.relay_from_to.get(next_relay.circuit_id, None)

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
            except CryptoException, e:
                self._logger.error(str(e))
                return False
            packet = plaintext + encrypted

            packet = TunnelConversion.swap_circuit_id(packet, message_type, circuit_id, next_relay.circuit_id)
            self.increase_bytes_sent(next_relay, self.send_packet(
                [Candidate(next_relay.sock_addr, False)], message_type, packet))

            return True
        return False

    def check_create(self, messages):
        for message in messages:
            if self.crypto.key.key_to_hash() != message.payload.node_id:
                yield DropMessage(message, "nodeids do not match")
                continue

            if self.crypto.key.pub().key_to_bin() != message.payload.node_public_key:
                yield DropMessage(message, "TunnelCommunity: public keys do not match")
                continue

            yield message

    def check_extend(self, messages):
        for message in messages:
            if not self.is_relay(message.payload.circuit_id):
                request = self.request_cache.get(u"anon-created", message.payload.circuit_id)
                if not request:
                    yield DropMessage(message, "invalid extend request circuit_id")
                    continue
            yield message

    def check_created(self, messages):
        for message in messages:
            if not self.is_relay(message.payload.circuit_id) and message.payload.circuit_id in self.circuits:
                request = self.request_cache.get(u"anon-circuit", message.payload.circuit_id)
                if not request:
                    yield DropMessage(message, "invalid created response circuit_id")
                    continue
            yield message

    def check_extended(self, messages):
        for message in messages:
            if not self.is_relay(message.payload.circuit_id):
                request = self.request_cache.get(u"anon-circuit", message.payload.circuit_id)
                if not request:
                    yield DropMessage(message, "invalid extended response circuit_id")
                    continue
            yield message

    def check_pong(self, messages):
        for message in messages:
            if not self.is_relay(message.payload.circuit_id):
                request = self.request_cache.get(u"ping", message.payload.identifier)
                if not request:
                    yield DropMessage(message, "invalid ping identifier")
                    continue
            yield message

    def _ours_on_created_extended(self, circuit, message):
        hop = circuit.unverified_hop

        try:
            shared_secret = self.crypto.verify_and_generate_shared_secret(
                hop.dh_secret, message.payload.key, message.payload.auth, hop.public_key.key.pk)
            hop.session_keys = self.crypto.generate_session_keys(shared_secret)

        except CryptoException:
            self.remove_circuit(circuit.circuit_id, "error while verifying shared secret, bailing out.")
            return

        circuit.add_hop(hop)
        circuit.unverified_hop = None

        if circuit.state == CIRCUIT_STATE_EXTENDING:

            if circuit.goal_hops - 1 == len(circuit.hops) and circuit.required_exit:
                host, port, pub_key = circuit.required_exit
                extend_hop_public_bin = pub_key
                extend_hop_addr = (host, port)

            else:
                candidate_list_enc = message.payload.candidate_list
                _, candidate_list = decode(self.crypto.decrypt_str(
                    candidate_list_enc, hop.session_keys[EXIT_NODE], hop.session_keys[EXIT_NODE_SALT]))

                ignore_candidates = [self.crypto.key_to_bin(hop.public_key) for hop in circuit.hops] + \
                                    [self.my_member.public_key]
                if circuit.required_exit:
                    ignore_candidates.append(circuit.required_exit[2])
                for ignore_candidate in ignore_candidates:
                    if ignore_candidate in candidate_list:
                        candidate_list.remove(ignore_candidate)

                for i in range(len(candidate_list) - 1, -1, -1):
                    public_key = self.crypto.key_from_public_bin(candidate_list[i])
                    if not self.crypto.is_key_compatible(public_key):
                        candidate_list.pop(i)

                extend_hop_public_bin = next(iter(candidate_list), None)
                extend_hop_addr = None

            if extend_hop_public_bin:
                extend_hop_public_key = self.dispersy.crypto.key_from_public_bin(extend_hop_public_bin)
                circuit.unverified_hop = Hop(extend_hop_public_key)
                circuit.unverified_hop.dh_secret, circuit.unverified_hop.dh_first_part = self.crypto.generate_diffie_secret(
                )

                self._logger.info(
                    "extending circuit %d with %s", circuit.circuit_id, extend_hop_public_bin[:20].encode('hex'))
                self.increase_bytes_sent(
                    circuit, self.send_cell([Candidate(circuit.first_hop, False)], u"extend", (circuit.circuit_id,
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

    def on_cell(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            self._logger.debug("Got %s (%d) from %s", message.payload.message_type,
                               message.payload.circuit_id, message.candidate.sock_addr)
            # TODO: if crypto fails for relay messages, call remove_relay
            # TODO: if crypto fails for other messages, call remove_circuit
            if not self.relay_cell(circuit_id, message.payload.message_type, message):

                plaintext, encrypted = TunnelConversion.split_encrypted_packet(message.packet, message.name)
                if message.payload.message_type not in [u'create', u'created']:
                    try:
                        encrypted = self.crypto_in(circuit_id, encrypted)
                    except CryptoException, e:
                        self._logger.error(str(e))
                        continue

                packet = plaintext + encrypted

                self.dispersy.on_incoming_packets(
                    [(message.candidate, TunnelConversion.convert_from_cell(packet))], False, source=u"circuit_%d" % circuit_id)

                if circuit_id in self.circuits:
                    self.circuits[circuit_id].beat_heart()
                    self.increase_bytes_received(self.circuits[circuit_id], len(message.packet))

    def on_create(self, messages):
        for message in messages:
            candidate = message.candidate
            circuit_id = message.payload.circuit_id

            if self.settings.max_relays_or_exits <= len(self.relay_from_to) + len(self.exit_sockets):
                self._logger.error('TunnelCommunity: ignoring create for circuit %d from %s (too many relays %d)',
                                   circuit_id, candidate.sock_addr, len(self.relay_from_to) + len(self.exit_sockets))
                continue

            if self._request_cache.has(u"anon-created", circuit_id):
                self._logger.error('TunnelCommunity: circuit_id collision in on_create (%d)', circuit_id)
                continue

            self.directions[circuit_id] = EXIT_NODE
            self._logger.info(
                'TunnelCommunity: we joined circuit %d with neighbour %s', circuit_id, candidate.sock_addr)

            shared_secret, Y, AUTH = self.crypto.generate_diffie_shared_secret(message.payload.key)
            self.relay_session_keys[circuit_id] = self.crypto.generate_session_keys(shared_secret)

            candidates = {}
            for c in self.dispersy_yield_verified_candidates():
                candidates[c.get_member().public_key] = c
                if len(candidates) >= 4:
                    break

            self.request_cache.add(CreatedRequestCache(self, circuit_id, candidate, candidates))
            if candidate._association is not None:
                candidate_mid = candidate._association.mid.encode('hex')
            else:
                candidate_mid = 0
            self.exit_sockets[circuit_id] = TunnelExitSocket(circuit_id, self, candidate.sock_addr, candidate_mid)

            if self.notifier:
                from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_JOINED
                self.notifier.notify(NTFY_TUNNEL, NTFY_JOINED, candidate.sock_addr, circuit_id)

            candidate_list_enc = self.crypto.encrypt_str(
                encode(candidates.keys()), *self.get_session_keys(self.relay_session_keys[circuit_id], EXIT_NODE))
            self.send_cell([candidate], u"created", (circuit_id, Y, AUTH, candidate_list_enc))

    def on_created(self, messages):
        for message in messages:
            candidate = message.candidate
            circuit_id = message.payload.circuit_id

            if circuit_id not in self.waiting_for:
                self._logger.error(
                    "Got an unexpected CREATED message for circuit %d from %s:%d", circuit_id, *candidate.sock_addr)
                continue
            self.waiting_for.remove(circuit_id)

            self.directions[circuit_id] = ORIGINATOR
            if circuit_id in self.relay_from_to:
                self._logger.debug("Got CREATED message forward as EXTENDED to origin.")

                forwarding_relay = self.relay_from_to[circuit_id]
                self.send_cell(
                    [Candidate(forwarding_relay.sock_addr, False)], u"extended", (forwarding_relay.circuit_id,
                                                                                  message.payload.key,
                                                                                  message.payload.auth,
                                                                                  message.payload.candidate_list))

            # Circuit is ours.
            if circuit_id in self.circuits:
                circuit = self.circuits[circuit_id]
                self._ours_on_created_extended(circuit, message)

    def on_extend(self, messages):
        for message in messages:
            if message.payload.node_public_key:
                candidate = message.candidate
                circuit_id = message.payload.circuit_id
                request = self.request_cache.pop(u"anon-created", circuit_id)

                if request.candidates.has_key(message.payload.node_public_key):
                    extend_candidate = request.candidates[message.payload.node_public_key]
                else:
                    extend_candidate = Candidate(message.payload.node_addr, False)

                self._logger.info("on_extend send CREATE for circuit (%s, %d) to %s:%d!", candidate.sock_addr,
                                  circuit_id, extend_candidate.sock_addr[0], extend_candidate.sock_addr[1])
            else:
                self._logger.error("cancelling EXTEND, no candidate!")
                continue

            if circuit_id in self.relay_from_to:
                current_relay = self.relay_from_to.pop(circuit_id)
                assert not current_relay.online, "shouldn't be called whenever relay is online the extend message should have been forwarded"

                # We will just forget the attempt and try again, possibly with another candidate.
                del self.relay_from_to[current_relay.circuit_id]

            new_circuit_id = self._generate_circuit_id(extend_candidate.sock_addr)

            self.waiting_for.add(new_circuit_id)
            self.relay_from_to[new_circuit_id] = RelayRoute(circuit_id, candidate.sock_addr, mid=candidate.get_member().mid.encode('hex'))
            self.relay_from_to[circuit_id] = RelayRoute(new_circuit_id, extend_candidate.sock_addr, mid=extend_candidate.get_member().mid.encode('hex'))

            self.relay_session_keys[new_circuit_id] = self.relay_session_keys[circuit_id]

            self.directions[new_circuit_id] = ORIGINATOR
            self.directions[circuit_id] = EXIT_NODE

            self.remove_exit_socket(circuit_id)

            self._logger.info("extending circuit, got candidate with IP %s:%d from cache", *extend_candidate.sock_addr)

            self.increase_bytes_sent(new_circuit_id, self.send_cell([extend_candidate], u"create", (new_circuit_id,
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

        self._logger.debug("Got data (%d) from %s", circuit_id, sock_addr)

        if not self.relay_packet(circuit_id, message_type, packet):
            plaintext, encrypted = TunnelConversion.split_encrypted_packet(packet, message_type)

            try:
                encrypted = self.crypto_in(circuit_id, encrypted, is_data=True)
            except CryptoException, e:
                self._logger.warning(str(e))
                return

            packet = plaintext + encrypted
            circuit_id, destination, origin, data = TunnelConversion.decode_data(packet)

            if circuit_id in self.circuits and origin and sock_addr == self.circuits[circuit_id].first_hop:
                self.circuits[circuit_id].beat_heart()
                self.increase_bytes_received(self.circuits[circuit_id], len(packet))

                if TunnelConversion.could_be_dispersy(data):
                    self._logger.error("Giving incoming data packet to dispersy")
                    self.dispersy.on_incoming_packets(
                        [(Candidate(origin, False), data[TUNNEL_PREFIX_LENGHT:])], False, source=u"circuit_%d" % circuit_id)
                else:
                    anon_seed = self.circuits[circuit_id].ctype == CIRCUIT_TYPE_RP
                    self.socks_server.on_incoming_from_tunnel(self, self.circuits[circuit_id], origin, data, anon_seed)

            # It is not our circuit so we got it from a relay, we need to EXIT it!
            else:
                self._logger.debug("data for circuit %d exiting tunnel (%s)", circuit_id, destination)
                if destination != ('0.0.0.0', 0):
                    self.exit_data(circuit_id, sock_addr, destination, data)
                else:
                    self._logger.error("cannot exit data, destination is 0.0.0.0:0")

    def on_ping(self, messages):
        for message in messages:
            if self.exit_sockets.keys():
                self.send_cell([message.candidate], u"pong", (message.payload.circuit_id, message.payload.identifier))
                self._logger.debug("Got ping from %s", message.candidate)
            else:
                self._logger.error("Got ping from %s (not responding)", message.candidate)

    def on_pong(self, messages):
        for message in messages:
            self.request_cache.pop(u"ping", message.payload.identifier)
            self._logger.debug("Got pong from %s", message.candidate)

    def do_ping(self):
        # Ping circuits. Pings are only sent to the first hop, subsequent hops will relay the ping.
        for circuit in self.circuits.values():
            if circuit.state == CIRCUIT_STATE_READY and circuit.ctype != CIRCUIT_TYPE_RENDEZVOUS:
                cache = self.request_cache.add(PingRequestCache(self, circuit))
                self.increase_bytes_sent(circuit, self.send_cell(
                    [Candidate(circuit.first_hop, False)], u"ping", (circuit.circuit_id, cache.number)))

    def on_destroy(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            cand_sock_addr = message.candidate.sock_addr
            self._logger.error("Got destroy from %s for circuit %s", message.candidate, circuit_id)

            if circuit_id in self.relay_from_to:
                self.remove_relay(circuit_id, "Got destroy", True, (circuit_id, cand_sock_addr))

            elif circuit_id in self.exit_sockets:
                self._logger.error("Got an exit socket %s %s", circuit_id, cand_sock_addr)
                if cand_sock_addr != self.exit_sockets[circuit_id].sock_addr:
                    self._logger.error("%s not allowed send destroy", cand_sock_addr)
                    continue
                self.remove_exit_socket(circuit_id, "Got destroy")

            elif circuit_id in self.circuits:
                self._logger.error("Got a circuit %s %s", circuit_id, cand_sock_addr)
                if cand_sock_addr != self.circuits[circuit_id].first_hop:
                    self._logger.error("%s not allowed send destroy", cand_sock_addr)
                    continue
                self.remove_circuit(circuit_id, "Got destroy")

            else:
                self._logger.error("Circuit is already removed? %s %s", circuit_id, cand_sock_addr)

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
                self._logger.error("Got stats request from unknown crawler %s", request.candidate.sock_addr)

    def on_stats_response(self, messages):
        for message in messages:
            request = self.request_cache.get(u"stats", message.payload.identifier)
            if not request:
                self._logger.error("Got unexpected stats response from %s", message.candidate.sock_addr)
                continue

            request.handler(message.candidate, message.payload.stats)
            self._logger.info("Received stats response %s", message.payload.stats)

    def do_stats(self, candidate, handler):
        cache = self.request_cache.add(StatsRequestCache(self, handler))
        meta = self.get_meta_message(u"stats-request")
        request = meta.impl(authentication=(self._my_member,),
                            distribution=(self.global_time,), payload=(cache.number,))
        self.send_packet([candidate], u"stats-request", request.packet)

    def tunnel_data_to_end(self, ultimate_destination, data, circuit):
        packet = TunnelConversion.encode_data(circuit.circuit_id, ultimate_destination, ('0.0.0.0', 0), data)
        self.increase_bytes_sent(circuit, self.send_data([Candidate(circuit.first_hop, False)], u'data', packet))

    def tunnel_data_to_origin(self, circuit_id, sock_addr, source_address, data):
        packet = TunnelConversion.encode_data(circuit_id, ('0.0.0.0', 0), source_address, data)
        self.send_data([Candidate(sock_addr, False)], u'data', packet)

    def exit_data(self, circuit_id, sock_addr, destination, data):
        if circuit_id in self.exit_sockets:
            if not self.exit_sockets[circuit_id].enabled:
                # We got the correct circuit_id, but from a wrong IP.
                assert sock_addr == self.exit_sockets[circuit_id].sock_addr, "%s != %s" % (
                    str(sock_addr), str(self.exit_sockets[circuit_id].sock_addr))
                self.exit_sockets[circuit_id].enable()
            try:
                self.exit_sockets[circuit_id].sendto(data, destination)
            except:
                self._logger.error("Dropping data packets while EXITing")
                print_exc()
        else:
            self._logger.error("Dropping data packets with unknown circuit_id")

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
            return self.crypto.encrypt_str(content, *self.get_session_keys(self.relay_session_keys[circuit_id], ORIGINATOR))
        raise CryptoException("Don't know how to encrypt outgoing message for circuit_id %d" % circuit_id)

    def crypto_in(self, circuit_id, content, is_data=False):
        circuit = self.circuits.get(circuit_id, None)
        if circuit and len(circuit.hops) > 0:
            # Remove all the encryption layers
            for hop in self.circuits[circuit_id].hops:
                content = self.crypto.decrypt_str(
                    content, hop.session_keys[ORIGINATOR], hop.session_keys[ORIGINATOR_SALT])
            if circuit and is_data and circuit.ctype in [CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP]:
                direction = int(circuit.ctype != CIRCUIT_TYPE_RP)
                direction_salt = direction + 2
                content = self.crypto.decrypt_str(
                    content, circuit.hs_session_keys[direction], circuit.hs_session_keys[direction_salt])
            return content
        elif circuit_id in self.relay_session_keys:
            return self.crypto.decrypt_str(content, self.relay_session_keys[circuit_id][EXIT_NODE], self.relay_session_keys[circuit_id][EXIT_NODE_SALT])
        raise CryptoException("Don't know how to decrypt incoming message for circuit_id %d" % circuit_id)

    def crypto_relay(self, circuit_id, content):
        direction = self.directions[circuit_id]
        if direction == ORIGINATOR:
            return self.crypto.encrypt_str(content, *self.get_session_keys(self.relay_session_keys[circuit_id], ORIGINATOR))
        elif direction == EXIT_NODE:
            return self.crypto.decrypt_str(content, self.relay_session_keys[circuit_id][EXIT_NODE], self.relay_session_keys[circuit_id][EXIT_NODE_SALT])
        raise CryptoException("Direction must be either ORIGINATOR or EXIT_NODE")

    def increase_bytes_sent(self, obj, num_bytes):
        if isinstance(obj, Circuit):
            obj.bytes_up += num_bytes
            self.stats['bytes_up'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_BYTES_SENT, obj.mid, num_bytes)
        elif isinstance(obj, RelayRoute):
            obj.bytes_up += num_bytes
            self.stats['bytes_relay_up'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_RELAY_BYTES_SENT, obj.mid, num_bytes)
        elif isinstance(obj, TunnelExitSocket):
            obj.bytes_up += num_bytes
            self.stats['bytes_exit'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT, obj.mid, num_bytes)

    def increase_bytes_received(self, obj, num_bytes):
        if isinstance(obj, Circuit):
            obj.bytes_down += num_bytes
            self.stats['bytes_down'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_BYTES_RECEIVED, obj.mid, num_bytes)
        elif isinstance(obj, RelayRoute):
            obj.bytes_down += num_bytes
            self.stats['bytes_relay_down'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_RELAY_BYTES_RECEIVED, obj.mid, num_bytes)
        elif isinstance(obj, TunnelExitSocket):
            obj.bytes_down += num_bytes
            self.stats['bytes_enter'] += num_bytes
            _barter_statistics.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, obj.mid, num_bytes)
