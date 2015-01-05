# Written by Egbert Bouman

import time
import os
import struct
import socket
from collections import defaultdict

from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED
from Tribler.Core.DecentralizedTracking.pymdht.core.identifier import Id
from Tribler.Core.Utilities.encoding import encode, decode

from Crypto.Util.number import bytes_to_long, long_to_bytes

from Tribler.community.tunnel import CIRCUIT_TYPE_IP, CIRCUIT_TYPE_RP, CIRCUIT_TYPE_INTRODUCE, CIRCUIT_TYPE_RENDEZVOUS

from Tribler.community.tunnel.payload import (EstablishIntroPayload, IntroEstablishedPayload, EstablishRendezvousPayload,
                                              RendezvousEstablishedPayload, Intro1Payload, Intro2Payload,
                                              Rendezvous1Payload, Rendezvous2Payload, KeysRequestPayload,
                                              KeysResponsePayload)
from Tribler.community.tunnel.routing import RelayRoute, IntroductionPoint, RendezvousPoint

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
from twisted.internet.task import LoopingCall


class IPRequestCache(RandomNumberCache):

    def __init__(self, community, circuit):
        super(IPRequestCache, self).__init__(community.request_cache, u"establish-intro")
        self.circuit = circuit
        self.community = community

    @property
    def timeout_delay(self):
        return 5.0

    def on_timeout(self):
        self._logger.debug("IPRequestCache: no response on establish-intro (circuit %d)", self.circuit.circuit_id)
        self.community.remove_circuit(self.circuit.circuit_id, 'establish-intro timeout')


class RPRequestCache(RandomNumberCache):

    def __init__(self, community, circuit):
        super(RPRequestCache, self).__init__(community.request_cache, u"establish-rendezvous")
        self.circuit = circuit
        self.community = community

    @property
    def timeout_delay(self):
        return 5.0

    def on_timeout(self):
        self._logger.debug("RPRequestCache: no response on establish-rendezvous (circuit %d)", self.circuit.circuit_id)
        self.community.remove_circuit(self.circuit.circuit_id, 'establish-rendezvous timeout')


class Introduce1RequestCache(RandomNumberCache):

    def __init__(self, community, circuit):
        super(Introduce1RequestCache, self).__init__(community.request_cache, u"intro1")
        self.circuit = circuit
        self.community = community

    @property
    def timeout_delay(self):
        return 20.0

    def on_timeout(self):
        self._logger.debug("Introduce1RequestCache: no response on intro1 (circuit %d)", self.circuit.circuit_id)
        self.community.remove_circuit(self.circuit.circuit_id, 'intro1 timeout')


class KeysRequestCache(RandomNumberCache):

    def __init__(self, community, callback):
        super(KeysRequestCache, self).__init__(community.request_cache, u"keys-request")
        self.callback = callback
        self.community = community

    def on_success(self, ip_key, service_key):
        self.callback(ip_key, service_key)

    @property
    def timeout_delay(self):
        return 5.0

    def on_timeout(self):
        pass


class HiddenTunnelCommunity(TunnelCommunity):

    def __init__(self, *args, **kwargs):
        super(HiddenTunnelCommunity, self).__init__(*args, **kwargs)

        self.my_intro_points = {}
        self.my_rendezvous_points = {}
        self.intro_point_for = {}
        self.rendezvous_point_for = {}
        self.download_states = {}
        self.rp_blacklist = defaultdict(dict)
        self.last_rp_creation = {}

    def initialize(self, tribler_session=None, settings=None):
        super(HiddenTunnelCommunity, self).initialize(tribler_session, settings)

        self.register_task("clean_rp_blacklist", LoopingCall(self.clean_rp_blacklist)).start(10)

    def initiate_meta_messages(self):
        return super(HiddenTunnelCommunity, self).initiate_meta_messages() + \
                [Message(self, u"establish-intro", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), EstablishIntroPayload(), self._generic_timeline_check,
                        self.on_establish_intro),
                Message(self, u"intro-established", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), IntroEstablishedPayload(), self.check_intro_established,
                        self.on_intro_established),
                Message(self, u"establish-rendezvous", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), EstablishRendezvousPayload(), self._generic_timeline_check,
                        self.on_establish_rendezvous),
                Message(self, u"rendezvous-established", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), RendezvousEstablishedPayload(), self.check_rendezvous_established,
                        self.on_rendezvous_established),
                Message(self, u"keys-request", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), KeysRequestPayload(), self._generic_timeline_check,
                        self.on_keys_request),
                Message(self, u"keys-response", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), KeysResponsePayload(), self._generic_timeline_check,
                        self.on_keys_response),
                Message(self, u"intro1", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), Intro1Payload(), self.check_intro1,
                        self.on_intro1),
                Message(self, u"intro2", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), Intro2Payload(), self.check_intro2,
                        self.on_intro2),
                Message(self, u"rendezvous1", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), Rendezvous1Payload(), self.check_rendezvous1,
                        self.on_rendezvous1),
                Message(self, u"rendezvous2", NoAuthentication(), PublicResolution(), DirectDistribution(),
                        CandidateDestination(), Rendezvous2Payload(), self.check_rendezvous2,
                        self.on_rendezvous2)]

    def remove_circuit(self, circuit_id, additional_info='', destroy=False, rebuild=False):
        super(HiddenTunnelCommunity, self).remove_circuit(circuit_id, additional_info, destroy, rebuild)

        # Remove & rebuild introduction/rendezvous points
        if circuit_id in self.my_intro_points:
            self._logger.debug("removed introduction point %s", ', rebuilding' if rebuild else '')
            ip = self.my_intro_points.pop(circuit_id)
            if rebuild:
                self.create_introduction_points(ip.info_hash, ip.circuit.goal_hops)

        if circuit_id in self.my_rendezvous_points:
            self._logger.error("removed rendezvous point %s", ', rebuilding' if rebuild else '')
            rp = self.my_rendezvous_points.pop(circuit_id)
            if rebuild:
                self.create_rendezvous_points(rp.info_hash, rp.circuit.goal_hops)



    def _generate_binary_string(self, length):
        return os.urandom(length)

    def _readable_binary_string(self, value):
        return value.encode('hex')[:20]

    def ip_to_circuit_id(self, ip_str):
        return struct.unpack("!I", socket.inet_aton(ip_str))[0]

    def circuit_id_to_ip(self, circuit_id):
        return socket.inet_ntoa(struct.pack("!I", circuit_id))

    def clean_rp_blacklist(self):
        for info_hash, peers in self.rp_blacklist.items():
            for sock_addr, ts in peers.items():
                if time.time() - ts > 60:
                    self.rp_blacklist[info_hash].pop(sock_addr)

    def monitor_downloads(self, dslist):
        # Monitor downloads with anonymous flag set, and build rendezvous/introduction points when needed.
        new_states = {}
        hops = {}

        for ds in dslist:
            download = ds.get_download()
            tdef = download.get_def()
            if tdef.get_def_type() == 'torrent' and tdef.is_anonymous():
                info_hash = tdef.get_infohash()
                hops[info_hash] = download.get_hops()
                new_states[info_hash] = ds.get_status()

        for info_hash in set(new_states.keys() + self.download_states.keys()):
            new_state = new_states.get(info_hash, None)
            old_state = self.download_states.get(info_hash, None)
            state_changed = new_state != old_state

            # Every 300s force a DHT check to discover new introduction points
            force_rendezvous = (time.time() - self.last_rp_creation.get(info_hash, 0)) >= 300

            if (state_changed or force_rendezvous) and new_state == DLSTATUS_DOWNLOADING:
                self.create_rendezvous_points(info_hash, hops=hops.get(info_hash, 2))

            elif state_changed and new_state == DLSTATUS_SEEDING:
                self.create_introduction_points(info_hash, hops=hops.get(info_hash, 2))

            elif state_changed and new_state in [DLSTATUS_STOPPED, None]:
                for cid, p in self.my_rendezvous_points.items() + self.my_intro_points.items():
                    if p.info_hash == info_hash:
                        self.remove_circuit(cid, 'download stopped', destroy=True, rebuild=False)

        self.download_states = new_states

    def create_introduction_points(self, info_hash, hops, amount=1):
        self._logger.debug('Creating %d introduction point(s)', amount)
        self._create_introduction_points(info_hash, hops, amount)

        # Ensures that libtorrent tries to make an outgoing connection so that the socks5 server
        # knows on which UDP port libtorrent is listening.
        self.trsession.get_download(info_hash).add_peer(('1.1.1.1' , 1024))

    @call_on_reactor_thread
    def _create_introduction_points(self, info_hash, hops, amount=1):

        def callback(circuit):
            # We got a circuit, now let's create a introduction point
            circuit_id = circuit.circuit_id
            service_key = self.crypto.generate_key(u"curve25519")
            ip = self.my_intro_points[circuit_id] = IntroductionPoint(circuit, info_hash, service_key,
                                                                      self.crypto.key_to_bin(service_key.pub()))
            cache = self.request_cache.add(IPRequestCache(self, circuit))
            payload = (circuit_id, cache.number, ip.service_key_public_bin, info_hash)
            self.send_cell([Candidate(circuit.first_hop, False)], u'establish-intro', payload)
            self._logger.debug("Establish introduction tunnel %s for service %s",
                               circuit_id, self._readable_binary_string(ip.service_key_public_bin))

        # Create circuits for introduction points
        for _ in range(0, amount):
            self.create_circuit(hops, CIRCUIT_TYPE_IP, callback, max_retries=5)

    def create_rendezvous_points(self, info_hash, hops):
        def add_peer(circuit_id, download):
            download.add_peer((self.circuit_id_to_ip(circuit_id), 1024))

        def dht_callback(ih, peers, _):
            if not peers:
                return

            exclude = [rp.intro_point[:2] for rp in self.my_rendezvous_points.values()] + \
                      self.rp_blacklist[ih].keys()

            for peer in set(peers):
                if peer not in exclude:
                    self._logger.error("Creating rendezvous point for introduction point %s", peer)
                    download = self.trsession.get_download(ih)
                    self._create_rendezvous_point(ih, peer, hops, lambda c, d=download: add_peer(c, d))
                    # Blacklist this sock_addr for a period of at least 60s
                    self.rp_blacklist[ih][peer] = time.time()

        self.last_rp_creation[info_hash] = time.time()

        # Get introduction points from the DHT, create rendezvous the points, and add the resulting
        # circuit_ids to the libtorrent download
        self.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), dht_callback)

    @call_on_reactor_thread
    def _create_rendezvous_point(self, info_hash, sock_addr, hops, finished_callback):

        def keys_callback(ip_key, service_key, sock_addr):
            def circuit_callback(circuit):
                # Now that we have a circuit + the required info, let's create a rendezvous point
                circuit_id = circuit.circuit_id
                rp = self.my_rendezvous_points[circuit_id] = RendezvousPoint(circuit, info_hash,
                                                                             self._generate_binary_string(20),
                                                                             service_key,
                                                                             (sock_addr[0], sock_addr[1], ip_key),
                                                                             finished_callback)
                cache = self.request_cache.add(RPRequestCache(self, circuit))
                payload = (circuit_id, cache.number, rp.cookie)
                self.send_cell([Candidate(circuit.first_hop, False)], u'establish-rendezvous', payload)
                self._logger.error("Establish rendezvous tunnel %s with cookie %s", circuit_id,
                                   self._readable_binary_string(rp.cookie))

            # Create a circuit for the rendezvous points
            self.create_circuit(hops, CIRCUIT_TYPE_RP, circuit_callback, max_retries=5)

        def request_keys(circuit):
            self._logger.error("Sending keys-request to %s", sock_addr)
            cache = self.request_cache.add(KeysRequestCache(self, lambda i, s, a=sock_addr: keys_callback(i, s, a)))
            meta = self.get_meta_message(u'keys-request')
            message = meta.impl(distribution=(self.global_time,), payload=(cache.number, info_hash))
            circuit.tunnel_data(sock_addr, TUNNEL_PREFIX + message.packet)

        circuit = self.selection_strategy.select(None, hops)
        if circuit:
            request_keys(circuit)
        else:
            self._logger.error("No circuit for keys-request")

    def check_intro_established(self, messages):
        for message in messages:
            request = self.request_cache.get(u"establish-intro", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid intro-established request identifier")
                continue
            yield message

    def check_rendezvous_established(self, messages):
        for message in messages:
            request = self.request_cache.get(u"establish-rendezvous", message.payload.identifier)
            if not request:
                yield DropMessage(message, "invalid rendezvous-established request identifier")
                continue
            yield message

    def check_intro1(self, messages):
        for message in messages:
            service_key = message.payload.service_key
            if service_key not in self.intro_point_for:
                yield DropMessage(message, "intro1 has unknown service_key")
                continue
            yield message

    def check_intro2(self, messages):
        for message in messages:
            circuit = self.circuits.get(message.payload.circuit_id, None)
            if not circuit or circuit.ctype != CIRCUIT_TYPE_IP:
                yield DropMessage(message, "got intro2 with invalid circuit_id")
                continue
            yield message

    def check_rendezvous1(self, messages):
        for message in messages:
            cookie = message.payload.cookie
            if cookie not in self.rendezvous_point_for:
                yield DropMessage(message, "rendezvous1 has unknown cookie")
                continue
            yield message

    def check_rendezvous2(self, messages):
        for message in messages:
            circuit = self.circuits.get(message.payload.circuit_id, None)
            if not circuit or circuit.ctype != CIRCUIT_TYPE_RP:
                yield DropMessage(message, "got rendezvous2 with invalid circuit_id")
                continue
            yield message

    def on_establish_intro(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            if circuit_id in self.exit_sockets:
                candidate = message.candidate
                if self.exit_sockets[circuit_id].enabled:
                    self._logger.error("Got establish-intro from %s but exit socket is enabled, " +
                                       "aborting.", candidate)
                    continue
                self.remove_exit_socket(circuit_id, 'exit socket becomes introduction point')
                self.intro_point_for[message.payload.service_key] = (circuit_id, message.payload.info_hash, candidate)
                self._logger.error("Establish-intro received from %s. Circuit %s associated with " +
                                   "service_key %s", candidate, circuit_id,
                                   self._readable_binary_string(message.payload.service_key))
                self.send_cell([candidate], u"intro-established", (circuit_id, message.payload.identifier))
                self.dht_announce(message.payload.info_hash)
            else:
                self._logger.error("Got establish-intro but no exit socket found")

    def on_intro_established(self, messages):
        for message in messages:
            self.request_cache.pop(u"establish-intro", message.payload.identifier)
            self._logger.info("Got intro-established from %s", message.candidate)

    def on_establish_rendezvous(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            if circuit_id in self.exit_sockets:
                if self.exit_sockets[circuit_id].enabled:
                    self._logger.error("Got establish-rendezvous from %s but exit socket is " +
                                       "enabled, aborting.", message.candidate)
                    continue
                self.remove_exit_socket(circuit_id, 'exit socket becomes rendezvous point')
                self.rendezvous_point_for[message.payload.cookie] = (circuit_id, message.candidate)
                self._logger.error("Establish-rendezvous received from %s. Circuit %s associated " +
                                   "with rendezvous cookie %s", message.candidate, circuit_id,
                                   self._readable_binary_string(message.payload.cookie))
                payload = (circuit_id, message.payload.identifier, self.dispersy.wan_address)
                self.send_cell([message.candidate], u"rendezvous-established", payload)
            else:
                self._logger.error("Got establish-rendezvous from %s but no exit socket found",
                                   message.candidate)

    def on_rendezvous_established(self, messages):
        for message in messages:
            cache = self.request_cache.pop(u"establish-rendezvous", message.payload.identifier)
            self._logger.error("Got rendezvous-established from %s", message.candidate)
            rp = self.my_rendezvous_points[cache.circuit.circuit_id]
            rp.rendezvous_point = list(message.payload.rendezvous_point_addr) + \
                                  [self.crypto.key_to_bin(rp.circuit.hops[-1].public_key)]
            self.send_intro1_over_new_tunnel(rp)

    def on_keys_request(self, messages):
        for message in messages:
            info_hash = message.payload.info_hash
            service_keys = [sk for sk, (_, ih, _) in self.intro_point_for.iteritems() if ih == info_hash]
            if service_keys:
                meta = self.get_meta_message(u'keys-response')
                payload = (message.payload.identifier, self.my_member.public_key, service_keys[0])
                response = meta.impl(distribution=(self.global_time,), payload=payload)
                self.send_packet([message.candidate], u'keys-response', response.packet)
                self._logger.error("keys-request received from %s, response sent", message.candidate)
            else:
                self._logger.error("Got keys-request but no service_key found")

    def on_keys_response(self, messages):
        for message in messages:
            cache = self.request_cache.get(u"keys-request", message.payload.identifier)
            if cache:
                cache.on_success(message.payload.ip_key, message.payload.service_key)
                self._logger.error("keys-response received from %s", message.candidate)
            else:
                self._logger.error("Unknown keys-response received from %s", message.candidate)

    def on_intro1(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            service_key = message.payload.service_key
            relay_circuit_id, _, relay_candidate = self.intro_point_for[service_key]
            self._logger.error("Got intro1 with rendezvous cookie %s via tunnel %s from %s",
                               self._readable_binary_string(message.payload.cookie), circuit_id, message.candidate)
            self.remove_exit_socket(circuit_id, 'intro1 received')

            payload = (relay_circuit_id, message.payload.identifier, message.payload.key,
                       message.payload.cookie, message.payload.rendezvous_point)
            self.send_cell([relay_candidate], u"intro2", payload)
            self._logger.error("Relayed intro1 as an intro2 message into tunnel %s", relay_circuit_id)

    def on_intro2(self, messages):
        for message in messages:
            # TODO: check for replay attack

            # Decrypt using hybrid crypto
            ip = self.my_intro_points[message.payload.circuit_id]
            decrypt = lambda item, sk = ip.service_key: self.crypto.ec_decrypt_str(sk, item)
            self.send_rendezvous1_over_new_tunnel(ip, message.payload.identifier,
                                                  decode(decrypt(message.payload.rendezvous_point))[1],
                                                  decrypt(message.payload.cookie), decrypt(message.payload.key))

    def on_rendezvous1(self, messages):
        for message in messages:
            circuit_id = message.payload.circuit_id
            cookie = message.payload.cookie
            relay_circuit_id, relay_candidate = self.rendezvous_point_for[cookie]
            self._logger.error("Got rendezvous1 with valid rendezvous cookie %s via tunnel %s " +
                               "from %s", self._readable_binary_string(cookie), circuit_id, message.candidate)

            self.remove_exit_socket(circuit_id, 'rendezvous1 received')

            payload = (relay_circuit_id, message.payload.identifier, message.payload.key)
            self.send_cell([relay_candidate], u"rendezvous2", payload)
            self._logger.error("Relayed rendezvous1 as rendezvous2 into %s", relay_circuit_id)

            self.relay_from_to[circuit_id] = RelayRoute(relay_circuit_id, relay_candidate.sock_addr, True)
            self.relay_from_to[relay_circuit_id] = RelayRoute(circuit_id, message.candidate.sock_addr, True)
            self._logger.error("Connected circuits %s and %s", circuit_id, relay_circuit_id)

    def on_rendezvous2(self, messages):
        for message in messages:
            self.request_cache.pop(u'intro1', message.payload.identifier)
            rp = self.my_rendezvous_points[message.payload.circuit_id]
            session_keys = self.crypto.generate_session_keys(rp.circuit.dh_secret, bytes_to_long(message.payload.key))
            rp.circuit.hs_session_keys = session_keys
            self._logger.error("Handshake completed!")
            self._logger.error("Session keys %s %s", self._readable_binary_string(session_keys[0]),
                                                                      self._readable_binary_string(session_keys[1]))
            rp.finished_callback(message.payload.circuit_id)

    def send_intro1_over_new_tunnel(self, rp):

        def callback(circuit):
            cache = self.request_cache.add(Introduce1RequestCache(self, circuit))
            self._logger.error("Send intro1 over tunnel %s with cookie %s",
                               circuit.circuit_id, self._readable_binary_string(rp.cookie))

            rp.circuit.dh_secret, rp.circuit.dh_first_part = self.crypto.generate_diffie_secret()

            # Partially encrypt payload using hybrid crypto
            sk = self.dispersy.crypto.key_from_public_bin(rp.service_key)
            encrypt = lambda item, sk = sk: self.crypto.ec_encrypt_str(sk, str(item))
            payload = (circuit.circuit_id, cache.number, encrypt((rp.circuit.dh_first_part)),
                       encrypt(rp.cookie), encrypt(encode(rp.rendezvous_point)), rp.service_key)

            self.send_cell([Candidate(circuit.first_hop, False)], u'intro1', tuple(payload))

        # Create circuit for intro1
        hops = rp.circuit.goal_hops
        self.create_circuit(hops, CIRCUIT_TYPE_INTRODUCE, callback, max_retries=5, required_exit=rp.intro_point)

    def send_rendezvous1_over_new_tunnel(self, ip, identifier, rendezvous_point, cookie, dh_first_part):

        def callback(circuit):
            self._logger.error("Send rendezvous1 over tunnel %s with cookie %s",
                               circuit.circuit_id, self._readable_binary_string(cookie))

            circuit.dh_secret, circuit.dh_second_part = self.crypto.generate_diffie_secret()
            session_keys = self.crypto.generate_session_keys(circuit.dh_secret, bytes_to_long(dh_first_part))
            circuit.hs_session_keys = session_keys
            self._logger.error("Session keys %s %s", self._readable_binary_string(session_keys[0]),
                                                                      self._readable_binary_string(session_keys[1]))
            payload = (circuit.circuit_id, identifier, long_to_bytes(circuit.dh_second_part), cookie)
            self.send_cell([Candidate(circuit.first_hop, False)], u'rendezvous1', payload)

        # Create circuit for rendezvous1
        hops = ip.circuit.goal_hops
        self.create_circuit(hops, CIRCUIT_TYPE_RENDEZVOUS, callback, max_retries=5, required_exit=rendezvous_point)

    def dht_announce(self, info_hash):
        # DHT announce
        if self.trsession:
            def cb(info_hash, peers, source):
                self._logger.error("Announced %s to the DHT", info_hash.encode('hex'))

            port = self.trsession.get_dispersy_port()
            self.trsession.lm.mainline_dht.get_peers(info_hash, Id(info_hash), cb, bt_port=port)
        else:
            self._logger.error("Need a Tribler session to announce to the DHT")
