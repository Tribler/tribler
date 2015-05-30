# Written by Egbert Bouman

import time
import os
import struct
import socket
import hashlib

from collections import defaultdict

from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED
from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id
from Tribler.Core.Utilities.encoding import encode, decode

from Tribler.community.tunnel import CIRCUIT_TYPE_IP, CIRCUIT_TYPE_RP, CIRCUIT_TYPE_RENDEZVOUS, \
                                     DEFAULT_HOPS, EXIT_NODE, EXIT_NODE_SALT

from Tribler.community.tunnel.payload import (EstablishIntroPayload, IntroEstablishedPayload,
                                              EstablishRendezvousPayload, RendezvousEstablishedPayload,
                                              KeyResponsePayload, KeyRequestPayload, CreateE2EPayload,
                                              CreatedE2EPayload, LinkE2EPayload, LinkedE2EPayload)
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


class IPRequestCache(RandomNumberCache):

    def __init__(self, community, circuit):
        super(IPRequestCache, self).__init__(community.request_cache, u"establish-intro")
        self.circuit = circuit
        self.community = community

    def on_timeout(self):
        self._logger.debug("IPRequestCache: no response on establish-intro (circuit %d)", self.circuit.circuit_id)
        self.community.remove_circuit(self.circuit.circuit_id, 'establish-intro timeout')


class RPRequestCache(RandomNumberCache):

    def __init__(self, community, rp):
        super(RPRequestCache, self).__init__(community.request_cache, u"establish-rendezvous")
        self.community = community
        self.rp = rp

    def on_timeout(self):
        self._logger.debug("RPRequestCache: no response on establish-rendezvous (circuit %d)", 
                           self.rp.circuit.circuit_id)
        self.community.remove_circuit(self.rp.circuit.circuit_id, 'establish-rendezvous timeout')


class KeyRequestCache(RandomNumberCache):

    def __init__(self, community, circuit, sock_addr, info_hash):
        super(KeyRequestCache, self).__init__(community.request_cache, u"key-request")
        self.circuit = circuit
        self.sock_addr = sock_addr
        self.info_hash = info_hash

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

        self.dht_blacklist = defaultdict(list)
        self.last_dht_lookup = {}

    def initiate_meta_messages(self):
        return super(HiddenTunnelCommunity, self).initiate_meta_messages() + \
            [Message(self, u"key-request", NoAuthentication(), PublicResolution(), DirectDistribution(),
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

    def remove_circuit(self, circuit_id, additional_info='', destroy=False, rebuild=False):
        super(HiddenTunnelCommunity, self).remove_circuit(circuit_id, additional_info, destroy, rebuild)

        # Remove & rebuild introduction/rendezvous points
        if circuit_id in self.my_intro_points:
            self._logger.debug("removed introduction point %s", ', rebuilding' if rebuild else '')
            downloads = self.my_intro_points.pop(circuit_id)
            if rebuild:
                for info_hash, hops in downloads:
                    self.create_introduction_points(info_hash, hops)

        if circuit_id in self.my_download_points:
            self._logger.error("removed rendezvous point %s", ', rebuilding' if rebuild else '')
            info_hash, hops, _ = self.my_download_points.pop(circuit_id)
            if rebuild:
                self.do_lookup(info_hash, hops)

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

        for info_hash in set(new_states.keys() + self.download_states.keys()):
            new_state = new_states.get(info_hash, None)
            old_state = self.download_states.get(info_hash, None)
            state_changed = new_state != old_state

            force_dht_lookup = (time.time() - self.last_dht_lookup.get(info_hash, 0)) >= 300

            if (state_changed or force_dht_lookup) and new_state == DLSTATUS_DOWNLOADING:
                self.do_lookup(info_hash, hops=hops.get(info_hash, 2))

            elif state_changed and new_state == DLSTATUS_SEEDING:
                self.create_introduction_point(info_hash, hops=hops.get(info_hash, DEFAULT_HOPS))

            elif state_changed and new_state in [DLSTATUS_STOPPED, None]:
                for cid, info_hash_hops in self.my_download_points.items():
                    if info_hash_hops[0] == info_hash:
                        self.remove_circuit(cid, 'download stopped', destroy=True, rebuild=False)

                for cid, info_hash_hops_list in self.my_intro_points.items():
                    for i in xrange(len(info_hash_hops_list) - 1, -1, -1):
                        if info_hash_hops[i][0] == info_hash:
                            info_hash_hops_list.pop(i)

                    if len(info_hash_hops_list) == 0:
                        self.remove_circuit(cid, 'all downloads stopped', destroy=True, rebuild=False)

        self.download_states = new_states

    def do_lookup(self, info_hash, hops):
        # Get seeders from the DHT and establish an e2e encrypted tunnel to them
        @call_on_reactor_thread
        def dht_callback(info_hash, peers, _):
            if not peers:
                return

            blacklist = self.dht_blacklist[info_hash]

            # cleanup dht_blacklist
            for i in xrange(len(blacklist) - 1, -1, -1):
                if time.time() - blacklist[i][0] > 60:
                    blacklist.pop(i)

            exclude = [rp[2] for rp in self.my_download_points.values()] + [sock_addr for _, sock_addr in blacklist]
            for peer in set(peers):
                if peer not in exclude:
                    self._logger.info("Requesting key from %s", peer)

                    # Blacklist this sock_addr for a period of at least 60s
                    self.dht_blacklist[info_hash].append((time.time(), peer))

                    self.create_key_request(info_hash, peer)

        self._logger.debug("Doing dht lookup for hidden community")
        self.last_dht_lookup[info_hash] = time.time()
        self.dht_lookup(info_hash, dht_callback)

    def create_key_request(self, info_hash, sock_addr):
        # 1. Select a circuit
        self._logger.debug("Create key request: select circuit")
        circuit = self.selection_strategy.select(None, DEFAULT_HOPS)
        if not circuit:
            self._logger.error("No circuit for key-request")
            return False

        # 2. Send a key-request message
        self._logger.debug("Create key request: send key request")
        cache = self.request_cache.add(KeyRequestCache(self, circuit, sock_addr, info_hash))
        meta = self.get_meta_message(u'key-request')
        message = meta.impl(distribution=(self.global_time,), payload=(cache.number, info_hash))
        circuit.tunnel_data(sock_addr, TUNNEL_PREFIX + message.packet)
        return True

    def check_key_request(self, messages):
        for message in messages:
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
            # if we have received this message over a socket, we need to forward it
            if not message.source.startswith(u"circuit_"):
                relay_circuit = self.intro_point_for[message.payload.info_hash]
                relay_circuit.tunnel_data(message.candidate.sock_addr, TUNNEL_PREFIX + message.packet)

            else:
                info_hash = message.payload.info_hash
                key = self.session_keys[info_hash]
                circuit = self.circuits[int(message.source[8:])]

                meta = self.get_meta_message(u'key-response')
                response = meta.impl(distribution=(self.global_time,), payload=(
                    message.payload.identifier, key.pub().key_to_bin()))
                circuit.tunnel_data(message.candidate.sock_addr, TUNNEL_PREFIX + response.packet)

    def check_key_response(self, messages):
        for message in messages:
            if not message.source.startswith(u"circuit_"):
                yield DropMessage(message, "must be received from a circuit")
                continue

            request = self.request_cache.get(u"key-request", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid key-response identifier")
                continue

            yield message

    def on_key_response(self, messages):
        for message in messages:
            cache = self.request_cache.pop(u"key-request", message.payload.identifier)
            self.create_e2e(cache.circuit, cache.sock_addr, cache.info_hash, message.payload.public_key)

    def create_e2e(self, circuit, sock_addr, info_hash, public_key):
        hop = Hop(self.crypto.key_from_public_bin(public_key))
        hop.dh_secret, hop.dh_first_part = self.crypto.generate_diffie_secret()

        cache = self.request_cache.add(E2ERequestCache(self, info_hash, circuit, hop, sock_addr))
        meta = self.get_meta_message(u'create-e2e')
        message = meta.impl(distribution=(self.global_time,), payload=(cache.number, info_hash, hop.node_id,
                                                                       hop.node_public_key, hop.dh_first_part))
        circuit.tunnel_data(sock_addr, TUNNEL_PREFIX + message.packet)

    def on_create_e2e(self, messages):
        for message in messages:
            # if we have received this message over a socket, we need to forward it
            if not message.source.startswith(u"circuit_"):
                self._logger.debug('On create e2e: forward message because received over socket')
                relay_circuit = self.intro_point_for[message.payload.info_hash]
                relay_circuit.tunnel_data(message.candidate.sock_addr, TUNNEL_PREFIX + message.packet)
            else:
                self._logger.debug('On create e2e: create rendezvous point')
                self.create_rendezvous_point(
                    DEFAULT_HOPS, lambda rendezvous_point, message=message: self.create_created_e2e(rendezvous_point, message))

    def create_created_e2e(self, rendezvous_point, message):
        info_hash = message.payload.info_hash
        key = self.session_keys[info_hash]

        circuit = self.circuits[int(message.source[8:])]
        shared_secret, Y, AUTH = self.crypto.generate_diffie_shared_secret(message.payload.key, key)
        rendezvous_point.circuit.hs_session_keys = self.crypto.generate_session_keys(shared_secret)
        rp_info_enc = self.crypto.encrypt_str(
            encode((rendezvous_point.rp_info, rendezvous_point.cookie)), *self.get_session_keys(rendezvous_point.circuit.hs_session_keys, EXIT_NODE))

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
            shared_secret = self.crypto.verify_and_generate_shared_secret(cache.hop.dh_secret, message.payload.key, 
                                                                          message.payload.auth, 
                                                                          cache.hop.public_key.key.pk)
            session_keys = self.crypto.generate_session_keys(shared_secret)

            _, rp_info = decode(self.crypto.decrypt_str(message.payload.rp_sock_addr, session_keys[EXIT_NODE], 
                                                        session_keys[EXIT_NODE_SALT]))

            self.create_circuit(DEFAULT_HOPS, CIRCUIT_TYPE_RENDEZVOUS, callback=lambda circuit,
                                cookie=rp_info[1], session_keys=session_keys, info_hash=cache.info_hash,
                                sock_addr=cache.sock_addr: self.create_link_e2e(circuit, cookie, session_keys,
                                                                                info_hash, sock_addr),
                                max_retries=5, required_exit=rp_info[0])

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

            self.relay_from_to[circuit.circuit_id] = RelayRoute(relay_circuit.circuit_id, relay_circuit.sock_addr, True)
            self.relay_from_to[relay_circuit.circuit_id] = RelayRoute(circuit.circuit_id, circuit.sock_addr, True)

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

            for download in self.trsession.get_downloads():
                if cache.info_hash == self.get_lookup_info_hash(download.get_def().get_infohash()):
                    download.add_peer((self.circuit_id_to_ip(cache.circuit.circuit_id), 1024))
                    break

    def create_introduction_point(self, info_hash, hops, amount=1):
        # Create a separate key per infohash
        if info_hash not in self.session_keys:
            self.session_keys[info_hash] = self.crypto.generate_key(u"curve25519")

        def callback(circuit):
            # We got a circuit, now let's create a introduction point
            circuit_id = circuit.circuit_id
            self.my_intro_points[circuit_id].append((info_hash, hops))

            cache = self.request_cache.add(IPRequestCache(self, circuit))
            self.send_cell([Candidate(circuit.first_hop, False)],
                           u'establish-intro', (circuit_id, cache.number, info_hash))
            self._logger.debug("Established introduction tunnel %s", circuit_id)

        for _ in range(amount):
            self.create_circuit(hops, CIRCUIT_TYPE_IP, callback, max_retries=5)

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
            self._logger.info("Got intro-established from %s", message.candidate)

    def create_rendezvous_point(self, hops, finished_callback):
        def callback(circuit):
            # We got a circuit, now let's create a rendezvous point
            circuit_id = circuit.circuit_id
            rp = RendezvousPoint(circuit, os.urandom(20), finished_callback)

            cache = self.request_cache.add(RPRequestCache(self, rp))
            self.send_cell([Candidate(circuit.first_hop, False)],
                           u'establish-rendezvous', (circuit_id, cache.number, rp.cookie))

        # create a new circuit to be used to transfer data
        self.create_circuit(hops, CIRCUIT_TYPE_RP, callback, max_retries=5)

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
            self._logger.error("Need a Tribler session to lookup to the DHT")

    def dht_announce(self, info_hash):
        if self.trsession:
            def cb(info_hash, peers, source):
                self._logger.error("Announced %s to the DHT", info_hash.encode('hex'))

            port = self.trsession.get_dispersy_port()
            self.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb, bt_port=port)
        else:
            self._logger.error("Need a Tribler session to announce to the DHT")

    def get_lookup_info_hash(self, info_hash):
        return hashlib.sha1('tribler anyonymous download' + info_hash.encode('hex')).digest()
    