# Written by Egbert Bouman

import time
import os
import struct
import socket
import hashlib

from collections import defaultdict

from Tribler.Core.simpledefs import DLSTATUS_SEEDING, DLSTATUS_STOPPED, \
    NTFY_TUNNEL, NTFY_IP_REMOVED, NTFY_RP_REMOVED, NTFY_IP_RECREATE, \
    NTFY_DHT_LOOKUP, NTFY_KEY_REQUEST, NTFY_KEY_RESPOND, NTFY_KEY_RESPONSE, \
    NTFY_CREATE_E2E, NTFY_ONCREATED_E2E, NTFY_IP_CREATED, DLSTATUS_DOWNLOADING
from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id
from Tribler.Core.Utilities.encoding import encode, decode

from Tribler.community.tunnel import CIRCUIT_TYPE_IP, CIRCUIT_TYPE_RP, CIRCUIT_TYPE_RENDEZVOUS, \
    EXIT_NODE, EXIT_NODE_SALT, CIRCUIT_ID_PORT

from Tribler.community.tunnel.payload import (EstablishIntroPayload, IntroEstablishedPayload,
                                              EstablishRendezvousPayload, RendezvousEstablishedPayload,
                                              KeyResponsePayload, KeyRequestPayload, CreateE2EPayload,
                                              CreatedE2EPayload, LinkE2EPayload, LinkedE2EPayload,
                                              DHTRequestPayload, DHTResponsePayload)
from Tribler.community.tunnel.routing import RelayRoute, RendezvousPoint, Hop

from Tribler.dispersy.authentication import NoAuthentication
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.endpoint import TUNNEL_PREFIX
from Tribler.dispersy.message import Message, DropMessage
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.community.tunnel.tunnel_community import TunnelCommunity
from Tribler.dispersy.requestcache import RandomNumberCache
import logging


class IPRequestCache(RandomNumberCache):

    def __init__(self, community, circuit):
        super(IPRequestCache, self).__init__(community.request_cache, u"establish-intro")
        self.tunnel_logger = logging.getLogger('TunnelLogger')
        self.circuit = circuit
        self.community = community

    def on_timeout(self):
        self.tunnel_logger.info("IPRequestCache: no response on establish-intro (circuit %d)", self.circuit.circuit_id)
        self.community.remove_circuit(self.circuit.circuit_id, 'establish-intro timeout')


class RPRequestCache(RandomNumberCache):

    def __init__(self, community, rp):
        super(RPRequestCache, self).__init__(community.request_cache, u"establish-rendezvous")
        self.tunnel_logger = logging.getLogger('TunnelLogger')
        self.community = community
        self.rp = rp

    def on_timeout(self):
        self.tunnel_logger.info("RPRequestCache: no response on establish-rendezvous (circuit %d)",
                                self.rp.circuit.circuit_id)
        self.community.remove_circuit(self.rp.circuit.circuit_id, 'establish-rendezvous timeout')


class KeyRequestCache(RandomNumberCache):

    def __init__(self, community, circuit, sock_addr, info_hash):
        super(KeyRequestCache, self).__init__(community.request_cache, u"key-request")
        self.tunnel_logger = logging.getLogger('TunnelLogger')
        self.circuit = circuit
        self.sock_addr = sock_addr
        self.info_hash = info_hash
        self.community = community

    def on_timeout(self):
        self.tunnel_logger.info("KeyRequestCache: no response on key-request to %s",
                                self.sock_addr)
        if self.info_hash in self.community.infohash_pex:
            self.tunnel_logger.info("Remove peer %s from the peer exchange cache" % repr(self.sock_addr))
            peers = self.community.infohash_pex[self.info_hash]
            for peer in peers.copy():
                peer_sock, _ = peer
                if self.sock_addr == peer_sock:
                    self.community.infohash_pex[self.info_hash].remove(peer)


class DHTRequestCache(RandomNumberCache):

    def __init__(self, community, circuit, info_hash):
        super(DHTRequestCache, self).__init__(community.request_cache, u"dht-request")
        self.circuit = circuit
        self.info_hash = info_hash

    def on_timeout(self):
        pass


class KeyRelayCache(RandomNumberCache):

    def __init__(self, community, identifier, sock_addr):
        super(KeyRelayCache, self).__init__(community.request_cache, u"key-request")
        self.identifier = identifier
        self.return_sock_addr = sock_addr

    def on_timeout(self):
        pass


class E2ERequestCache(RandomNumberCache):

    def __init__(self, community, info_hash, circuit, hop, sock_addr):
        super(E2ERequestCache, self).__init__(community.request_cache, u"e2e-request")
        self.circuit = circuit
        self.hop = hop
        self.info_hash = info_hash
        self.sock_addr = sock_addr

    def on_timeout(self):
        pass


class LinkRequestCache(RandomNumberCache):

    def __init__(self, community, circuit, info_hash):
        super(LinkRequestCache, self).__init__(community.request_cache, u"link-request")
        self.circuit = circuit
        self.info_hash = info_hash

    def on_timeout(self):
        pass


class HiddenTunnelCommunity(TunnelCommunity):

    def __init__(self, *args, **kwargs):
        super(HiddenTunnelCommunity, self).__init__(*args, **kwargs)

        self.session_keys = {}
        self.download_states = {}

        self.my_intro_points = defaultdict(list)
        self.my_download_points = {}

        self.intro_point_for = {}
        self.rendezvous_point_for = {}
        self.infohash_rp_circuits = defaultdict(list)
        self.infohash_ip_circuits = defaultdict(list)
        self.infohash_pex = defaultdict(set)

        self.dht_blacklist = defaultdict(list)
        self.last_dht_lookup = {}

        self.tunnel_logger = logging.getLogger('TunnelLogger')

        self.hops = {}

    def initiate_meta_messages(self):
        return super(HiddenTunnelCommunity, self).initiate_meta_messages() + \
            [Message(self, u"dht-request", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), DHTRequestPayload(), self._generic_timeline_check,
                     self.on_dht_request),
             Message(self, u"dht-response", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), DHTResponsePayload(), self.check_dht_response,
                     self.on_dht_response),
             Message(self, u"key-request", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), KeyRequestPayload(), self.check_key_request,
                     self.on_key_request),
             Message(self, u"key-response", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), KeyResponsePayload(), self.check_key_response,
                     self.on_key_response),
             Message(self, u"create-e2e", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), CreateE2EPayload(), self.check_key_request,
                     self.on_create_e2e),
             Message(self, u"created-e2e", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), CreatedE2EPayload(), self.check_created_e2e,
                     self.on_created_e2e),
             Message(self, u"link-e2e", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), LinkE2EPayload(), self.check_link_e2e,
                     self.on_link_e2e),
             Message(self, u"linked-e2e", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), LinkedE2EPayload(), self.check_linked_e2e,
                     self.on_linked_e2e),
             Message(self, u"establish-intro", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), EstablishIntroPayload(), self.check_establish_intro,
                     self.on_establish_intro),
             Message(self, u"intro-established", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), IntroEstablishedPayload(), self.check_intro_established,
                     self.on_intro_established),
             Message(self, u"establish-rendezvous", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), EstablishRendezvousPayload(), self.check_establish_rendezvous,
                     self.on_establish_rendezvous),
             Message(self, u"rendezvous-established", NoAuthentication(), PublicResolution(), DirectDistribution(),
                     CandidateDestination(), RendezvousEstablishedPayload(), self.check_rendezvous_established,
                     self.on_rendezvous_established)]

    def remove_circuit(self, circuit_id, additional_info='', destroy=False):
        super(HiddenTunnelCommunity, self).remove_circuit(circuit_id, additional_info, destroy)

        if circuit_id in self.my_intro_points:
            if self.notifier:
                self.notifier.notify(NTFY_TUNNEL, NTFY_IP_REMOVED, circuit_id)
            self.tunnel_logger.info("removed introduction point %d" % circuit_id)
            self.my_intro_points.pop(circuit_id)

        if circuit_id in self.my_download_points:
            if self.notifier:
                self.notifier.notify(NTFY_TUNNEL, NTFY_RP_REMOVED, circuit_id)
            self.tunnel_logger.info("removed rendezvous point %d" % circuit_id)
            self.my_download_points.pop(circuit_id)

    def ip_to_circuit_id(self, ip_str):
        return struct.unpack("!I", socket.inet_aton(ip_str))[0]

    def circuit_id_to_ip(self, circuit_id):
        return socket.inet_ntoa(struct.pack("!I", circuit_id))

    @call_on_reactor_thread
    def monitor_downloads(self, dslist):
        # Monitor downloads with anonymous flag set, and build rendezvous/introduction points when needed.
        new_states = {}
        hops = {}

        for ds in dslist:
            download = ds.get_download()
            if download.get_hops() > 0:
                # Convert the real infohash to the infohash used for looking up introduction points
                real_info_hash = download.get_def().get_infohash()
                info_hash = self.get_lookup_info_hash(real_info_hash)
                hops[info_hash] = download.get_hops()
                new_states[info_hash] = ds.get_status()

        self.hops = hops

        for info_hash in set(new_states.keys() + self.download_states.keys()):
            new_state = new_states.get(info_hash, None)
            old_state = self.download_states.get(info_hash, None)
            state_changed = new_state != old_state

            # Stop creating introduction points if the download doesn't exist anymore
            if info_hash in self.infohash_ip_circuits and new_state == None:
                del self.infohash_ip_circuits[info_hash]

            # If the introducing circuit does not exist anymore or timed out: Build a new circuit
            if info_hash in self.infohash_ip_circuits:
                for (circuit_id, time_created) in self.infohash_ip_circuits[info_hash]:
                    if circuit_id not in self.my_intro_points and time_created < time.time() - 30:
                        self.infohash_ip_circuits[info_hash].remove((circuit_id, time_created))
                        if self.notifier:
                            self.notifier.notify(NTFY_TUNNEL, NTFY_IP_RECREATE, circuit_id, info_hash.encode('hex')[:6])
                        self.tunnel_logger.info('Recreate the introducing circuit for %s' % info_hash.encode('hex'))
                        self.create_introduction_point(info_hash)

            time_elapsed = (time.time() - self.last_dht_lookup.get(info_hash, 0))
            force_dht_lookup = time_elapsed >= self.settings.dht_lookup_interval
            if (state_changed or force_dht_lookup) and \
               (new_state == DLSTATUS_SEEDING or new_state == DLSTATUS_DOWNLOADING):
                self.tunnel_logger.info('Do dht lookup to find hidden services peers for %s' % info_hash.encode('hex'))
                self.do_dht_lookup(info_hash)

            if state_changed and new_state == DLSTATUS_SEEDING:
                self.create_introduction_point(info_hash)

            elif state_changed and new_state in [DLSTATUS_STOPPED, None]:
                if info_hash in self.infohash_pex:
                    self.infohash_pex.pop(info_hash)

                for cid, info_hash_hops in self.my_download_points.items():
                    if info_hash_hops[0] == info_hash:
                        self.remove_circuit(cid, 'download stopped', destroy=True)

                for cid, info_hash_list in self.my_intro_points.items():
                    for i in xrange(len(info_hash_list) - 1, -1, -1):
                        if info_hash_list[i] == info_hash:
                            info_hash_list.pop(i)

                    if len(info_hash_list) == 0:
                        self.remove_circuit(cid, 'all downloads stopped', destroy=True)

        self.download_states = new_states

    def do_dht_lookup(self, info_hash):
        # Select a circuit from the pool of exit circuits
        self.tunnel_logger.info("Do DHT request: select circuit")
        circuit = self.selection_strategy.select(None, self.hops[info_hash])
        if not circuit:
            self.tunnel_logger.info("No circuit for dht-request")
            return False

        # Send a dht-request message over this circuit
        self.tunnel_logger.info("Do DHT request: send dht request")
        self.last_dht_lookup[info_hash] = time.time()
        cache = self.request_cache.add(DHTRequestCache(self, circuit, info_hash))
        self.send_cell([Candidate(circuit.first_hop, False)],
                       u"dht-request",
                       (circuit.circuit_id, cache.number, info_hash))

    def on_dht_request(self, messages):
        for message in messages:
            info_hash = message.payload.info_hash

            @call_on_reactor_thread
            def dht_callback(info_hash, peers, _):
                if not peers:
                    peers = []
                meta = self.get_meta_message(u'dht-response')
                circuit_id = message.payload.circuit_id
                # Send the list of peers for this info_hash back to the requester
                dht_response_message = meta.impl(distribution=(self.global_time,), payload=(message.payload.circuit_id,
                                                                                            message.payload.identifier,
                                                                                            message.payload.info_hash,
                                                                                            encode(peers)))
                if circuit_id in self.exit_sockets:
                    circuit = self.exit_sockets[circuit_id]
                    circuit.tunnel_data(message.candidate.sock_addr, TUNNEL_PREFIX + dht_response_message.packet)
                else:
                    self.tunnel_logger.info("Circuit %d is not existing anymore, can't send back dht-response" %
                                            circuit_id)

            self.tunnel_logger.info("Doing dht hidden seeders lookup for info_hash %s" % info_hash.encode('HEX'))
            self.dht_lookup(info_hash, dht_callback)

    def check_dht_response(self, messages):
        for message in messages:
            if not self.is_relay(message.payload.circuit_id):
                request = self.request_cache.get(u"dht-request", message.payload.identifier)
                if not request:
                    yield DropMessage(message, "invalid dht-response identifier")
                    continue

            yield message

    def on_dht_response(self, messages):
        for message in messages:
            self.request_cache.pop(u"dht-request", message.payload.identifier)

            info_hash = message.payload.info_hash
            _, peers = decode(message.payload.peers)
            peers = set(peers)
            self.tunnel_logger.info("Received dht response containing %d peers" % len(peers))

            blacklist = self.dht_blacklist[info_hash]

            if self.notifier:
                self.notifier.notify(NTFY_TUNNEL, NTFY_DHT_LOOKUP, info_hash.encode('hex')[:6], peers)

            # cleanup dht_blacklist
            for i in xrange(len(blacklist) - 1, -1, -1):
                if time.time() - blacklist[i][0] > 60:
                    blacklist.pop(i)
            exclude = [rp[2] for rp in self.my_download_points.values()] + [sock_addr for _, sock_addr in blacklist]
            for peer in peers:
                if peer not in exclude:
                    self.tunnel_logger.info("Requesting key from dht peer %s", peer)
                    # Blacklist this sock_addr for a period of at least 60s
                    self.dht_blacklist[info_hash].append((time.time(), peer))
                    self.create_key_request(info_hash, peer)

    def create_key_request(self, info_hash, sock_addr):
        # 1. Select a circuit
        self.tunnel_logger.info("Create key request: select circuit")
        circuit = self.selection_strategy.select(None, self.hops[info_hash])
        if not circuit:
            self.tunnel_logger.error("No circuit for key-request")
            return

        # 2. Send a key-request message
        self.tunnel_logger.info("Create key request: send key request")
        if self.notifier:
            self.notifier.notify(NTFY_TUNNEL, NTFY_KEY_REQUEST, info_hash.encode('hex')[:6], sock_addr)
        cache = self.request_cache.add(KeyRequestCache(self, circuit, sock_addr, info_hash))
        meta = self.get_meta_message(u'key-request')
        message = meta.impl(distribution=(self.global_time,), payload=(cache.number, info_hash))
        circuit.tunnel_data(sock_addr, TUNNEL_PREFIX + message.packet)

    def check_key_request(self, messages):
        for message in messages:
            self.tunnel_logger.info("Check key request")
            info_hash = message.payload.info_hash
            if not message.source.startswith(u"circuit_"):
                if info_hash not in self.intro_point_for:
                    yield DropMessage(message, "not an intro point for this infohash")
                    continue
            else:
                if info_hash not in self.session_keys:
                    yield DropMessage(message, "not seeding this infohash")
                    continue

            yield message

    def on_key_request(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                # The intropoint receives the message over a socket, and forwards it to the seeder
                self.tunnel_logger.info("On key request: relay key request")
                cache = self.request_cache.add(KeyRelayCache(self,
                                                             message.payload.identifier,
                                                             message.candidate.sock_addr))
                meta = self.get_meta_message(u'key-request')
                message = meta.impl(distribution=(self.global_time,), payload=(cache.number, message.payload.info_hash))
                relay_circuit = self.intro_point_for[message.payload.info_hash]
                relay_circuit.tunnel_data(self.dispersy.wan_address, TUNNEL_PREFIX + message.packet)
            else:
                # The seeder responds with keys back to the intropoint
                info_hash = message.payload.info_hash
                key = self.session_keys[info_hash]
                circuit = self.circuits[int(message.source[8:])]
                if self.notifier:
                    self.notifier.notify(NTFY_TUNNEL, NTFY_KEY_RESPOND, info_hash.encode('hex')[:6], circuit.circuit_id)
                self.tunnel_logger.info("On key request: respond with keys to %s" % repr(message.candidate.sock_addr))
                meta = self.get_meta_message(u'key-response')
                pex_peers = self.infohash_pex.get(info_hash, set())
                response = meta.impl(distribution=(self.global_time,), payload=(
                    message.payload.identifier, key.pub().key_to_bin(),
                    encode(list(pex_peers)[:50])))
                circuit.tunnel_data(message.candidate.sock_addr, TUNNEL_PREFIX + response.packet)

    def check_key_response(self, messages):
        for message in messages:
            self.tunnel_logger.info("Check key response")
            request = self.request_cache.get(u"key-request", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid key-response identifier")
                continue
            yield message

    def on_key_response(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                cache = self.request_cache.pop(u"key-request", message.payload.identifier)
                self.tunnel_logger.info('On key response: forward message because received over socket')
                meta = self.get_meta_message(u'key-response')
                relay_message = meta.impl(distribution=(self.global_time,),
                                          payload=(cache.identifier, message.payload.public_key,
                                                   message.payload.pex_peers))
                self.send_packet([Candidate(cache.return_sock_addr, False)],
                                 u"key-response",
                                 TUNNEL_PREFIX + relay_message.packet)
            else:
                # pop key-request cache and notify gui
                self.tunnel_logger.info("On key response: received keys")
                cache = self.request_cache.pop(u"key-request", message.payload.identifier)
                _, pex_peers = decode(message.payload.pex_peers)
                if self.notifier:
                    self.notifier.notify(NTFY_TUNNEL, NTFY_KEY_RESPONSE, cache.info_hash.encode('hex')[:6],
                                         cache.circuit.circuit_id)

                # Cache this peer and key for pex via key-response
                self.tunnel_logger.info("Added key to peer exchange cache")
                self.infohash_pex[cache.info_hash].add((cache.sock_addr, message.payload.public_key))

                # Add received pex_peers to own list of known peers for this infohash
                for pex_peer in pex_peers:
                    pex_peer_sock, pex_peer_key = pex_peer
                    self.infohash_pex[cache.info_hash].add((pex_peer_sock, pex_peer_key))

                # Initate end-to-end circuits for all known peers in the pex list
                for peer in self.infohash_pex[cache.info_hash]:
                    peer_sock, peer_key = peer
                    if cache.info_hash not in self.infohash_ip_circuits:
                        self.tunnel_logger.info("Create end-to-end on pex_peer %s" % repr(peer_sock))
                        self.create_e2e(cache.circuit, peer_sock, cache.info_hash, peer_key)

    def create_e2e(self, circuit, sock_addr, info_hash, public_key):
        hop = Hop(self.crypto.key_from_public_bin(public_key))
        hop.dh_secret, hop.dh_first_part = self.crypto.generate_diffie_secret()
        if self.notifier:
            self.notifier.notify(NTFY_TUNNEL, NTFY_CREATE_E2E, info_hash.encode('hex')[:6])
        self.tunnel_logger.info("Create end to end initiated here")
        cache = self.request_cache.add(E2ERequestCache(self, info_hash, circuit, hop, sock_addr))
        meta = self.get_meta_message(u'create-e2e')
        message = meta.impl(distribution=(self.global_time,), payload=(cache.number, info_hash, hop.node_id,
                                                                       hop.node_public_key, hop.dh_first_part))
        circuit.tunnel_data(sock_addr, TUNNEL_PREFIX + message.packet)

    def on_create_e2e(self, messages):
        for message in messages:
            # if we have received this message over a socket, we need to forward it
            if not message.source.startswith(u"circuit_"):
                self.tunnel_logger.info('On create e2e: forward message because received over socket')
                relay_circuit = self.intro_point_for[message.payload.info_hash]
                relay_circuit.tunnel_data(message.candidate.sock_addr, TUNNEL_PREFIX + message.packet)
            else:
                self.tunnel_logger.info('On create e2e: create rendezvous point')
                self.create_rendezvous_point(self.hops[message.payload.info_hash],
                                             lambda rendezvous_point, message=message:
                                             self.create_created_e2e(rendezvous_point,
                                             message), message.payload.info_hash)

    def create_created_e2e(self, rendezvous_point, message):
        info_hash = message.payload.info_hash
        key = self.session_keys[info_hash]

        circuit = self.circuits[int(message.source[8:])]
        shared_secret, Y, AUTH = self.crypto.generate_diffie_shared_secret(message.payload.key, key)
        rendezvous_point.circuit.hs_session_keys = self.crypto.generate_session_keys(shared_secret)
        rp_info_enc = self.crypto.encrypt_str(
            encode((rendezvous_point.rp_info, rendezvous_point.cookie)),
            *self.get_session_keys(rendezvous_point.circuit.hs_session_keys, EXIT_NODE))

        meta = self.get_meta_message(u'created-e2e')
        response = meta.impl(distribution=(self.global_time,), payload=(
            message.payload.identifier, Y, AUTH, rp_info_enc))
        circuit.tunnel_data(message.candidate.sock_addr, TUNNEL_PREFIX + response.packet)

    def check_created_e2e(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                yield DropMessage(message, "must be received from a circuit")
                continue

            request = self.request_cache.get(u"e2e-request", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid created-e2e identifier")
                continue

            yield message

    def on_created_e2e(self, messages):
        for message in messages:
            cache = self.request_cache.pop(u"e2e-request", message.payload.identifier)
            shared_secret = self.crypto.verify_and_generate_shared_secret(cache.hop.dh_secret,
                                                                          message.payload.key,
                                                                          message.payload.auth,
                                                                          cache.hop.public_key.key.pk)
            session_keys = self.crypto.generate_session_keys(shared_secret)

            _, decoded = decode(self.crypto.decrypt_str(message.payload.rp_sock_addr,
                                                        session_keys[EXIT_NODE],
                                                        session_keys[EXIT_NODE_SALT]))
            rp_info, cookie = decoded

            if self.notifier:
                self.notifier.notify(NTFY_TUNNEL, NTFY_ONCREATED_E2E, cache.info_hash.encode('hex')[:6], rp_info)

            # Since it is the seeder that chose the rendezvous_point, we're essentially losing 1 hop of anonymity
            # at the downloader end. To compensate we add an extra hop.
            required_exit = Candidate(rp_info[:2], False)
            required_exit.associate(self.get_member(public_key=rp_info[2]))
            self.create_circuit(self.hops[cache.info_hash] + 1,
                                CIRCUIT_TYPE_RENDEZVOUS,
                                callback=lambda circuit, cookie=cookie, session_keys=session_keys,
                                info_hash=cache.info_hash, sock_addr=cache.sock_addr: self.create_link_e2e(circuit,
                                                                                                           cookie,
                                                                                                           session_keys,
                                                                                                           info_hash,
                                                                                                           sock_addr),
                                required_exit=required_exit,
                                info_hash=cache.info_hash)

    def create_link_e2e(self, circuit, cookie, session_keys, info_hash, sock_addr):
        self.my_download_points[circuit.circuit_id] = (info_hash, circuit.goal_hops, sock_addr)
        circuit.hs_session_keys = session_keys

        cache = self.request_cache.add(LinkRequestCache(self, circuit, info_hash))
        self.send_cell([Candidate(circuit.first_hop, False)], u'link-e2e', (circuit.circuit_id, cache.number, cookie))

    def check_link_e2e(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                yield DropMessage(message, "must be received from a circuit")
                continue

            if message.payload.cookie not in self.rendezvous_point_for:
                yield DropMessage(message, "not a rendezvous point for this cookie")
                continue

            circuit_id = int(message.source[8:])
            if self.exit_sockets[circuit_id].enabled:
                yield DropMessage(message, "exit socket for circuit is enabled, cannot link")
                continue

            relay_circuit = self.rendezvous_point_for[message.payload.cookie]
            if self.exit_sockets[relay_circuit.circuit_id].enabled:
                yield DropMessage(message, "exit socket for relay_circuit is enabled, cannot link")
                continue

            yield message

    def on_link_e2e(self, messages):
        for message in messages:
            circuit = self.exit_sockets[int(message.source[8:])]
            relay_circuit = self.rendezvous_point_for[message.payload.cookie]

            self.remove_exit_socket(circuit.circuit_id, 'linking circuit')
            self.remove_exit_socket(relay_circuit.circuit_id, 'linking circuit')

            self.send_cell([message.candidate], u"linked-e2e", (circuit.circuit_id, message.payload.identifier))

            self.relay_from_to[circuit.circuit_id] = RelayRoute(relay_circuit.circuit_id, relay_circuit.sock_addr, True,
                                                                mid=relay_circuit.mid)
            self.relay_from_to[relay_circuit.circuit_id] = RelayRoute(circuit.circuit_id, circuit.sock_addr, True,
                                                                      mid=circuit.mid)

    def check_linked_e2e(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                yield DropMessage(message, "must be received from a circuit")
                continue

            request = self.request_cache.get(u"link-request", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid linked-e2e identifier")
                continue

            yield message

    def on_linked_e2e(self, messages):
        for message in messages:
            cache = self.request_cache.pop(u"link-request", message.payload.identifier)
            download = self.find_download(cache.info_hash)
            if download:
                download.add_peer((self.circuit_id_to_ip(cache.circuit.circuit_id), CIRCUIT_ID_PORT))
            else:
                self.tunnel_logger.error('On linked e2e: could not find download!')

    def find_download(self, lookup_info_hash):
        for download in self.trsession.get_downloads():
            if lookup_info_hash == self.get_lookup_info_hash(download.get_def().get_infohash()):
                return download

    def create_introduction_point(self, info_hash, amount=1):
        # Create a separate key per infohash
        self.find_download(info_hash).add_peer(('1.1.1.1', 1024))

        if info_hash not in self.session_keys:
            self.session_keys[info_hash] = self.crypto.generate_key(u"curve25519")

        def callback(circuit):
            # We got a circuit, now let's create an introduction point
            circuit_id = circuit.circuit_id
            self.my_intro_points[circuit_id].append((info_hash))

            cache = self.request_cache.add(IPRequestCache(self, circuit))
            self.send_cell([Candidate(circuit.first_hop, False)],
                           u'establish-intro', (circuit_id, cache.number, info_hash))
            self.tunnel_logger.info("Established introduction tunnel %s", circuit_id)
            if self.notifier:
                self.notifier.notify(NTFY_TUNNEL, NTFY_IP_CREATED, info_hash.encode('hex')[:6], circuit_id)

        for _ in range(amount):
            # Create a circuit to the introduction point + 1 hop, to prevent the introduction
            # point from knowing what the seeder is seeding
            circuit_id = self.create_circuit(self.hops[info_hash] + 1,
                                             CIRCUIT_TYPE_IP,
                                             callback,
                                             info_hash=info_hash)
            self.infohash_ip_circuits[info_hash].append((circuit_id, time.time()))

    def check_establish_intro(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                yield DropMessage(message, "did not receive this message from a circuit")
                continue

            yield message

    def on_establish_intro(self, messages):
        for message in messages:
            circuit = self.exit_sockets[int(message.source[8:])]
            self.intro_point_for[message.payload.info_hash] = circuit

            self.send_cell([message.candidate], u"intro-established", (circuit.circuit_id, message.payload.identifier))
            self.dht_announce(message.payload.info_hash)

    def check_intro_established(self, messages):
        for message in messages:
            request = self.request_cache.get(u"establish-intro", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid intro-established request identifier")
                continue

            yield message

    def on_intro_established(self, messages):
        for message in messages:
            self.request_cache.pop(u"establish-intro", message.payload.identifier)
            self.tunnel_logger.info("Got intro-established from %s", message.candidate)

    def create_rendezvous_point(self, hops, finished_callback, info_hash):
        def callback(circuit):
            # We got a circuit, now let's create a rendezvous point
            circuit_id = circuit.circuit_id
            rp = RendezvousPoint(circuit, os.urandom(20), finished_callback)

            cache = self.request_cache.add(RPRequestCache(self, rp))
            if self.notifier:
                self.notifier.notify(NTFY_TUNNEL, NTFY_IP_CREATED, info_hash.encode('hex')[:6], circuit_id)

            self.send_cell([Candidate(circuit.first_hop, False)],
                           u'establish-rendezvous', (circuit_id, cache.number, rp.cookie))

        # create a new circuit to be used for transferring data
        circuit_id = self.create_circuit(hops,
                                         CIRCUIT_TYPE_RP,
                                         callback,
                                         info_hash=info_hash)
        self.infohash_rp_circuits[info_hash].append(circuit_id)

    def check_establish_rendezvous(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                yield DropMessage(message, "did not receive this message from a circuit")
                continue

            yield message

    def on_establish_rendezvous(self, messages):
        for message in messages:
            circuit = self.exit_sockets[int(message.source[8:])]
            self.rendezvous_point_for[message.payload.cookie] = circuit

            self.send_cell([message.candidate], u"rendezvous-established", (
                circuit.circuit_id, message.payload.identifier, self.dispersy.wan_address))

    def check_rendezvous_established(self, messages):
        for message in messages:
            request = self.request_cache.get(u"establish-rendezvous", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid rendezvous-established request identifier")
                continue

            yield message

    def on_rendezvous_established(self, messages):
        for message in messages:
            rp = self.request_cache.pop(u"establish-rendezvous", message.payload.identifier).rp

            sock_addr = message.payload.rendezvous_point_addr
            rp.rp_info = (sock_addr[0], sock_addr[1], self.crypto.key_to_bin(rp.circuit.hops[-1].public_key))
            rp.finished_callback(rp)

    def dht_lookup(self, info_hash, cb):
        if self.trsession:
            self.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb)
        else:
            self.tunnel_logger.error("Need a Tribler session to lookup to the DHT")

    def dht_announce(self, info_hash):
        if self.trsession:
            def cb(info_hash, peers, source):
                self.tunnel_logger.info("Announced %s to the DHT", info_hash.encode('hex'))

            port = self.trsession.get_dispersy_port()
            self.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb, bt_port=port)
        else:
            self.tunnel_logger.error("Need a Tribler session to announce to the DHT")

    def get_lookup_info_hash(self, info_hash):
        return hashlib.sha1('tribler anonymous download' + info_hash.encode('hex')).digest()
